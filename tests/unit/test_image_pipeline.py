"""Pipeline de imagem: moderacao, original privado, marca/metadados."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.image_generation.adapters.ai_agents.orchestrator import LangGraphImageAgent
from modules.image_generation.adapters.ai_agents.providers import make_png_bytes
from modules.image_generation.application.ports import EngineImage
from modules.image_generation.domain.entities import Generation, GenerationKind
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from shared_kernel.security_errors import (
    ImageBlockedError,
    ImageModerationUnavailableError,
)
from tests.conftest import InMemoryObjectStorage


class AllowingModerator:
    def __init__(self) -> None:
        self.calls = 0

    async def moderate(self, image_bytes):
        from modules.image_generation.application.ports.image_moderation import (
            ImageModerationResult,
            ImageModerationScores,
        )

        self.calls += 1
        return ImageModerationResult(scores=ImageModerationScores())


class BlockingModerator:
    def __init__(self, category: str = "nsfw") -> None:
        self.category = category
        self.calls = 0

    async def moderate(self, image_bytes):
        from modules.image_generation.application.ports.image_moderation import (
            ImageModerationResult,
            ImageModerationScores,
        )
        from modules.image_generation.domain.moderation import ModerationCategory

        self.calls += 1
        field = "sexual" if self.category == "nsfw" else self.category
        scores = ImageModerationScores(**{field: 0.99})
        return ImageModerationResult(
            scores=scores, blocked_category=ModerationCategory(self.category)
        )


class FailingModerator:
    async def moderate(self, image_bytes):
        raise ImageModerationUnavailableError()


class FakeWatermarker:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def apply(self, image_bytes: bytes) -> bytes:
        self.calls += 1
        if self.fail:
            raise RuntimeError("watermark failed")
        import io

        from PIL import Image, ImageDraw

        image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            [image.width - 2, image.height - 2, image.width - 1, image.height - 1],
            fill=(255, 0, 0, 255),
        )
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()


class FakeMetadata:
    def __init__(self) -> None:
        self.calls = 0

    def apply(self, image_bytes: bytes, *, model_name: str, created_at=None) -> bytes:
        self.calls += 1
        assert model_name
        return image_bytes


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, prompt, width, height, seed, on_progress):
        self.calls += 1
        await on_progress(90)
        return EngineImage(
            image_bytes=make_png_bytes(width, height),
            width=width,
            height=height,
            seed=1,
            duration_seconds=0.1,
        )


class FakeEditor(FakeGenerator):
    async def edit(self, *, prompt, source_image, width, height, seed, on_progress):
        self.calls += 1
        await on_progress(90)
        return EngineImage(
            image_bytes=make_png_bytes(width, height),
            width=width,
            height=height,
            seed=1,
            duration_seconds=0.1,
        )


def _agent(
    *,
    moderator=None,
    watermarker=None,
    metadata=None,
    storage=None,
    generator=None,
    editor=None,
):
    return LangGraphImageAgent(
        prompt_guard=PromptInjectionGuard(),
        generator=generator or FakeGenerator(),
        editor=editor or FakeEditor(),
        storage=storage or InMemoryObjectStorage(),
        image_moderator=moderator or AllowingModerator(),
        image_moderation_enabled=True,
        watermarker=watermarker or FakeWatermarker(),
        metadata_writer=metadata or FakeMetadata(),
    )


@pytest.mark.unit
async def test_gera_original_privado_e_resultado_com_marca() -> None:
    storage = InMemoryObjectStorage()
    watermarker = FakeWatermarker()
    metadata = FakeMetadata()
    generator = FakeGenerator()
    agent = _agent(
        storage=storage, watermarker=watermarker, metadata=metadata, generator=generator
    )
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )

    url = await agent.run_generation(generation, _noop)

    original_key = f"generations/{generation.id}/original.png"
    result_key = f"generations/{generation.id}/result.png"
    assert generation.original_object_key == original_key
    assert generation.result_object_key == result_key
    assert set(storage.objects) == {original_key, result_key}
    assert storage.objects[original_key] != storage.objects[result_key]
    assert watermarker.calls == 1
    assert metadata.calls == 1
    assert url and "result.png" in url


@pytest.mark.unit
async def test_saida_bloqueada_nao_grava_nada() -> None:
    storage = InMemoryObjectStorage()
    watermarker = FakeWatermarker()
    agent = _agent(
        storage=storage,
        watermarker=watermarker,
        moderator=BlockingModerator("nsfw"),
    )
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )

    with pytest.raises(ImageBlockedError) as exc:
        await agent.run_generation(generation, _noop)

    assert exc.value.code == "image_blocked_nsfw"
    assert exc.value.layer == "image_output"
    assert exc.value.penalize is False
    assert storage.objects == {}
    assert watermarker.calls == 0
    assert generation.original_object_key is None


@pytest.mark.unit
async def test_entrada_bloqueada_apaga_origem_e_nao_chama_motor() -> None:
    storage = InMemoryObjectStorage()
    source_key = "sources/1/source.png"
    await storage.put_object(source_key, make_png_bytes(64, 64))
    generator = FakeGenerator()
    moderator = BlockingModerator("gore")
    agent = _agent(storage=storage, generator=generator, moderator=moderator)
    generation = Generation(
        user_id=uuid4(),
        kind=GenerationKind.EDIT,
        prompt="edite",
        source_object_key=source_key,
    )

    with pytest.raises(ImageBlockedError) as exc:
        await agent.run_generation(generation, _noop)

    assert exc.value.code == "source_image_blocked_gore"
    assert exc.value.layer == "image_input"
    assert exc.value.penalize is True
    assert generator.calls == 0
    assert source_key not in storage.objects


@pytest.mark.unit
async def test_refino_nao_repassa_pela_moderacao_de_entrada() -> None:
    storage = InMemoryObjectStorage()
    moderator = AllowingModerator()
    agent = _agent(storage=storage, moderator=moderator)
    generation = Generation(
        user_id=uuid4(),
        kind=GenerationKind.EDIT,
        prompt="edite",
        source_object_key="generations/parent/original.png",
    )
    state = {"generation": generation}
    await agent._moderate_source(state)
    assert moderator.calls == 0
    assert "source_image_bytes" not in state


@pytest.mark.unit
async def test_falha_da_marca_limpa_original() -> None:
    storage = InMemoryObjectStorage()
    agent = _agent(storage=storage, watermarker=FakeWatermarker(fail=True))
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )

    with pytest.raises(RuntimeError):
        await agent.run_generation(generation, _noop)

    assert storage.objects == {}
    assert generation.original_object_key is None


@pytest.mark.unit
async def test_moderador_indisponivel_fail_closed() -> None:
    storage = InMemoryObjectStorage()
    agent = _agent(storage=storage, moderator=FailingModerator())
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )
    with pytest.raises(ImageModerationUnavailableError):
        await agent.run_generation(generation, _noop)
    assert storage.objects == {}


async def _noop(_: int) -> None:
    return None
