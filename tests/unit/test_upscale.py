"""Upscale: limite diario, original privado, lanczos/esrgan e falhas."""

from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image
from prometheus_client import REGISTRY

from modules.image_generation.adapters.ai_agents.providers import make_png_bytes
from modules.image_generation.adapters.upscale import (
    EsrganUpscaler,
    LanczosUpscaler,
    build_esrgan_command,
)
from modules.image_generation.application.ports import EngineImage
from modules.image_generation.application.use_cases.create_upscale import CreateUpscale
from modules.image_generation.application.use_cases.process_upscale import ProcessUpscale
from modules.image_generation.domain.engine_errors import EngineTimeoutError
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from modules.prompt_quota.domain.entities import PromptQuota
from shared_kernel.errors import DomainError, ForbiddenError, QuotaExceededError
from shared_kernel.security_errors import UpscaleLimitExceededError
from tests.conftest import (
    InMemoryGenerationRepository,
    InMemoryObjectStorage,
    SpyEventPublisher,
    SpyTaskQueue,
)

PNG_32 = make_png_bytes(32, 32)


class FakeQuota:
    def __init__(self, remaining: int = 5) -> None:
        self.remaining = remaining
        self.consumed = 0
        self.released = 0
        self.release_ok = True

    async def consume(self, *, principal_id, total):
        if self.remaining <= 0:
            raise QuotaExceededError(
                "limite", retry_after_seconds=3600,
                details={"next_available_at": 0},
            )
        self.consumed += 1
        self.remaining -= 1
        return PromptQuota(
            chances_remaining=self.remaining,
            chances_total=total,
            next_available_at=None,
        )

    async def release(self, *, principal_id):
        self.released += 1
        if self.release_ok:
            self.remaining += 1
        return self.release_ok

    async def get_quota(self, *, principal_id, total):
        return PromptQuota(
            chances_remaining=self.remaining,
            chances_total=total,
            next_available_at=None,
        )


class FakeUpscaler:
    def __init__(
        self,
        *,
        fail: Exception | None = None,
        size: tuple[int, int] | None = None,
    ) -> None:
        self.fail = fail
        self.size = size
        self.calls = 0

    async def upscale(self, image_bytes: bytes, *, factor: int = 2):
        self.calls += 1
        if self.fail:
            raise self.fail
        image = Image.open(io.BytesIO(image_bytes))
        width, height = self.size or (image.width * factor, image.height * factor)
        data = make_png_bytes(width, height)
        return EngineImage(
            image_bytes=data, width=width, height=height, seed=0, duration_seconds=0.1
        )


class FakeWatermarker:
    def __init__(self) -> None:
        self.calls = 0

    def apply(self, image_bytes: bytes) -> bytes:
        self.calls += 1
        width = int.from_bytes(image_bytes[16:20], "big")
        height = int.from_bytes(image_bytes[20:24], "big")
        return make_png_bytes(width, height)


class FakeMetadata:
    def __init__(self) -> None:
        self.calls = 0

    def apply(self, image_bytes: bytes, *, model_name: str, created_at=None) -> bytes:
        self.calls += 1
        return image_bytes


def _done(user_id, **kwargs) -> Generation:
    generation = Generation(
        user_id=user_id,
        kind=GenerationKind.GENERATE,
        prompt="um castelo",
        **kwargs,
    )
    generation.transition_to(GenerationStatus.PROCESSING)
    generation.transition_to(GenerationStatus.DONE)
    return generation


@pytest.mark.unit
async def test_lanczos_amplia_2x() -> None:
    result = await LanczosUpscaler().upscale(PNG_32)
    assert (result.width, result.height) == (64, 64)


@pytest.mark.unit
def test_comando_esrgan_com_espacos() -> None:
    command = build_esrgan_command(
        binary_path="C:/Program Files/sd/sd.exe",
        model_path="C:/Meus Modelos/up scaler.bin",
        input_path="C:/Temp A/source image.png",
        output_path="C:/Temp A/output image.png",
    )
    assert command[0] == "C:/Program Files/sd/sd.exe"
    assert "C:/Meus Modelos/up scaler.bin" in command
    assert command[command.index("-i") + 1] == "C:/Temp A/source image.png"
    assert command[command.index("-o") + 1] == "C:/Temp A/output image.png"


@pytest.mark.unit
async def test_esrgan_com_executavel_falso(fake_sd_cli, tmp_path) -> None:
    settings = SimpleNamespace(
        sdcpp_binary_path=str(fake_sd_cli),
        sdcpp_upscale_model_path="modelo falso.bin",
        upscale_timeout_seconds=10,
        min_free_ram_mb=1,
        cooldown_seconds_between_jobs=0.0,
    )
    upscaler = EsrganUpscaler(
        settings, available_ram_mb_fn=lambda: 16000
    )
    result = await upscaler.upscale(PNG_32)
    assert (result.width, result.height) == (64, 64)


@pytest.mark.unit
async def test_esrgan_timeout_mata_processo(fake_sd_cli) -> None:
    settings = SimpleNamespace(
        sdcpp_binary_path=str(fake_sd_cli),
        sdcpp_upscale_model_path="timeout.bin",
        upscale_timeout_seconds=1,
        min_free_ram_mb=1,
        cooldown_seconds_between_jobs=0.0,
    )
    upscaler = EsrganUpscaler(settings, available_ram_mb_fn=lambda: 16000)
    with pytest.raises(EngineTimeoutError):
        await upscaler.upscale(PNG_32)


@pytest.mark.unit
async def test_create_upscale_valida_dono_e_cria_parent(sample_user) -> None:
    repo = InMemoryGenerationRepository()
    parent = _done(
        sample_user.id,
        original_object_key="generations/p/original.png",
        result_object_key="generations/p/result.png",
    )
    await repo.save(parent)
    queue = SpyTaskQueue()
    quota = FakeQuota()
    use_case = CreateUpscale(
        generations=repo,
        task_queue=queue,
        quota_store=quota,
        daily_limit=5,
        events=SpyEventPublisher(),
    )
    output = await use_case.execute(
        generation_id=parent.id, user=sample_user, locale="pt-BR"
    )
    assert output.kind is GenerationKind.UPSCALE
    assert output.parent_generation_id == parent.id
    assert output.upscale_remaining == 4
    saved = await repo.get_by_id(output.id)
    assert saved is not None
    assert saved.source_object_key == parent.original_object_key
    assert queue.kinds == ["upscale"]
    assert sample_user.generation_credits == 5


@pytest.mark.unit
async def test_create_upscale_rejeita_nao_dono(sample_user) -> None:
    repo = InMemoryGenerationRepository()
    parent = _done(uuid4(), original_object_key="generations/p/original.png")
    await repo.save(parent)
    use_case = CreateUpscale(
        generations=repo,
        task_queue=SpyTaskQueue(),
        quota_store=FakeQuota(),
        daily_limit=5,
    )
    with pytest.raises(ForbiddenError):
        await use_case.execute(generation_id=parent.id, user=sample_user)


@pytest.mark.unit
async def test_create_upscale_rejeita_sem_original(sample_user) -> None:
    repo = InMemoryGenerationRepository()
    parent = _done(sample_user.id, result_object_key="generations/p/result.png")
    await repo.save(parent)
    use_case = CreateUpscale(
        generations=repo,
        task_queue=SpyTaskQueue(),
        quota_store=FakeQuota(),
        daily_limit=5,
    )
    with pytest.raises(DomainError):
        await use_case.execute(generation_id=parent.id, user=sample_user)


@pytest.mark.unit
async def test_create_upscale_limite_localizado(sample_user) -> None:
    repo = InMemoryGenerationRepository()
    parent = _done(sample_user.id, original_object_key="generations/p/original.png")
    await repo.save(parent)
    use_case = CreateUpscale(
        generations=repo,
        task_queue=SpyTaskQueue(),
        quota_store=FakeQuota(remaining=0),
        daily_limit=5,
    )
    with pytest.raises(UpscaleLimitExceededError) as exc:
        await use_case.execute(
            generation_id=parent.id, user=sample_user, locale="en"
        )
    assert exc.value.code == "upscale_limit_reached"
    assert "daily upscale limit" in exc.value.message
    assert (
        REGISTRY.get_sample_value("aimaginator_upscale_limit_hits_total") or 0
    ) >= 1


@pytest.mark.unit
async def test_process_upscale_grava_original_e_resultado(sample_user) -> None:
    repo = InMemoryGenerationRepository()
    parent = _done(sample_user.id, original_object_key="generations/p/original.png")
    await repo.save(parent)
    generation = Generation(
        user_id=sample_user.id,
        kind=GenerationKind.UPSCALE,
        prompt="um castelo",
        source_object_key=parent.original_object_key,
        parent_generation_id=parent.id,
    )
    await repo.save(generation)
    storage = InMemoryObjectStorage()
    await storage.put_object(parent.original_object_key, PNG_32)
    quota = FakeQuota()
    watermarker = FakeWatermarker()
    metadata = FakeMetadata()
    use_case = ProcessUpscale(
        generations=repo,
        storage=storage,
        upscaler=FakeUpscaler(),
        watermarker=watermarker,
        metadata_writer=metadata,
        events=SpyEventPublisher(),
        quota_store=quota,
    )
    await use_case.execute(generation.id)
    saved = await repo.get_by_id(generation.id)
    assert saved is not None and saved.status is GenerationStatus.DONE
    original_key = f"generations/{generation.id}/original.png"
    result_key = f"generations/{generation.id}/result.png"
    assert saved.original_object_key == original_key
    assert saved.result_object_key == result_key
    assert set(storage.objects) >= {original_key, result_key}
    assert watermarker.calls == 1
    assert metadata.calls == 1
    assert quota.released == 0
    assert saved.upscale_refunded is False


@pytest.mark.unit
async def test_process_upscale_falha_devolve_limite(sample_user) -> None:
    repo = InMemoryGenerationRepository()
    parent = _done(sample_user.id, original_object_key="generations/p/original.png")
    await repo.save(parent)
    generation = Generation(
        user_id=sample_user.id,
        kind=GenerationKind.UPSCALE,
        prompt="um castelo",
        source_object_key=parent.original_object_key,
        parent_generation_id=parent.id,
    )
    await repo.save(generation)
    storage = InMemoryObjectStorage()
    await storage.put_object(parent.original_object_key, PNG_32)
    quota = FakeQuota()
    use_case = ProcessUpscale(
        generations=repo,
        storage=storage,
        upscaler=FakeUpscaler(fail=EngineTimeoutError()),
        watermarker=FakeWatermarker(),
        metadata_writer=FakeMetadata(),
        events=SpyEventPublisher(),
        quota_store=quota,
    )
    with pytest.raises(EngineTimeoutError):
        await use_case.execute(generation.id)
    saved = await repo.get_by_id(generation.id)
    assert saved is not None and saved.status is GenerationStatus.FAILED
    assert saved.error_code == "engine_timeout"
    assert saved.upscale_refunded is True
    assert quota.released == 1
    assert set(storage.objects) == {parent.original_object_key}
