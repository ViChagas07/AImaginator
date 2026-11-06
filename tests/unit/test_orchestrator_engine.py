"""Testes do orquestrador com as portas ImageGenerator/ImageEditor."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.image_generation.adapters.ai_agents.orchestrator import LangGraphImageAgent
from modules.image_generation.adapters.ai_agents.providers import make_png_bytes
from modules.image_generation.application.ports import EngineImage
from modules.image_generation.domain.entities import (
    AspectRatio,
    Generation,
    GenerationKind,
)
from modules.image_generation.domain.image_bytes import InvalidImageBytesError
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from tests.conftest import InMemoryObjectStorage


class FakeGenerator:
    def __init__(self, data: bytes | None = None) -> None:
        self.calls: list[dict] = []
        self.data = data
        self.progress_seen: list[int] = []

    async def generate(self, *, prompt, width, height, seed, on_progress):
        self.calls.append(
            {"prompt": prompt, "width": width, "height": height, "seed": seed}
        )
        for percent in (10, 50, 90):
            self.progress_seen.append(percent)
            await on_progress(percent)
        return EngineImage(
            image_bytes=self.data or make_png_bytes(width, height),
            width=width,
            height=height,
            seed=seed or 99,
            duration_seconds=1.0,
        )


class FakeEditor(FakeGenerator):
    def __init__(self, data: bytes | None = None) -> None:
        super().__init__(data)
        self.sources: list[bytes] = []

    async def edit(self, *, prompt, source_image, width, height, seed, on_progress):
        self.sources.append(source_image)
        self.calls.append(
            {"prompt": prompt, "width": width, "height": height, "seed": seed}
        )
        for percent in (10, 50, 90):
            self.progress_seen.append(percent)
            await on_progress(percent)
        return EngineImage(
            image_bytes=self.data or make_png_bytes(width, height),
            width=width,
            height=height,
            seed=seed or 99,
            duration_seconds=1.0,
        )


class RecordingProcessor:
    def __init__(self) -> None:
        self.calls = 0

    def process(self, image: EngineImage, generation: Generation) -> EngineImage:
        self.calls += 1
        assert generation.id
        return image


def _agent(*, generator=None, editor=None, storage=None, processors=None):
    return LangGraphImageAgent(
        prompt_guard=PromptInjectionGuard(),
        generator=generator or FakeGenerator(),
        editor=editor or FakeEditor(),
        storage=storage or InMemoryObjectStorage(),
        post_processors=processors,
    )


@pytest.mark.unit
async def test_geracao_usa_generator_e_persiste_resultado() -> None:
    storage = InMemoryObjectStorage()
    generator = FakeGenerator()
    agent = _agent(generator=generator, storage=storage)
    generation = Generation(
        user_id=uuid4(),
        kind=GenerationKind.GENERATE,
        prompt="um castelo nas nuvens",
        aspect_ratio=AspectRatio.FOUR_THREE,
    )
    progress: list[int] = []

    async def collect(percent: int) -> None:
        progress.append(percent)

    url = await agent.run_generation(generation, collect)

    assert generator.calls[0]["width"] == 576
    assert generator.calls[0]["height"] == 448
    assert url.endswith(f"generations/{generation.id}/result.png?signature=test")
    assert generation.result_object_key == f"generations/{generation.id}/result.png"
    assert generation.seed == 99
    assert progress[0] >= 10
    assert progress[-1] == 99


@pytest.mark.unit
async def test_edicao_usa_editor_e_origem_do_storage() -> None:
    storage = InMemoryObjectStorage()
    editor = FakeEditor()
    agent = _agent(editor=editor, storage=storage)
    generation = Generation(
        user_id=uuid4(),
        kind=GenerationKind.EDIT,
        prompt="troque o ceu",
        aspect_ratio=AspectRatio.SQUARE,
        source_object_key="sources/123/source.png",
    )
    source = make_png_bytes(32, 32)
    await storage.put_object("sources/123/source.png", source)

    url = await agent.run_generation(generation, _noop)

    assert editor.sources == [source]
    assert "generations/" in url
    assert editor.calls[0]["seed"] is None


@pytest.mark.unit
async def test_pos_processador_e_chamado_antes_do_upload() -> None:
    storage = InMemoryObjectStorage()
    processor = RecordingProcessor()
    agent = _agent(storage=storage, processors=[processor])
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )

    await agent.run_generation(generation, _noop)

    assert processor.calls == 1
    assert len(storage.objects) == 2
    assert f"generations/{generation.id}/original.png" in storage.objects


@pytest.mark.unit
async def test_bytes_invalidos_nao_sao_persistidos() -> None:
    storage = InMemoryObjectStorage()
    agent = _agent(generator=FakeGenerator(data=b"not-an-image"), storage=storage)
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )

    with pytest.raises(InvalidImageBytesError):
        await agent.run_generation(generation, _noop)

    assert storage.objects == {}


@pytest.mark.unit
async def test_dimensoes_divergentes_nao_sao_persistidas() -> None:
    storage = InMemoryObjectStorage()
    generator = FakeGenerator(data=make_png_bytes(64, 64))
    agent = _agent(generator=generator, storage=storage)
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )

    with pytest.raises(InvalidImageBytesError):
        await agent.run_generation(generation, _noop)

    assert storage.objects == {}


async def _noop(_: int) -> None:
    return None
