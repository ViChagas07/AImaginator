"""Backfill de originais: dry-run, copia e metadados pos-processados."""

from __future__ import annotations

import io
from uuid import uuid4

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from modules.image_generation.application.services.backfill import (
    BackfillOriginalsService,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from tests.conftest import InMemoryGenerationRepository, InMemoryObjectStorage


def _png(*, metadata: bool) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (8, 8), "red")
    info = PngInfo()
    if metadata:
        info.add_text("DigitalSourceType", "trainedAlgorithmicMedia")
    image.save(output, format="PNG", pnginfo=info)
    return output.getvalue()


def _generation() -> Generation:
    generation = Generation(user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="x")
    generation.transition_to(GenerationStatus.PROCESSING)
    generation.attach_result(
        "https://storage.test/result.png",
        object_key=f"generations/{generation.id}/result.png",
    )
    return generation


@pytest.mark.unit
async def test_copia_resultado_sem_metadados_quando_apply() -> None:
    repo = InMemoryGenerationRepository()
    storage = InMemoryObjectStorage()
    generation = _generation()
    await repo.save(generation)
    storage.objects[generation.result_object_key] = _png(metadata=False)

    report = await BackfillOriginalsService(generations=repo, storage=storage, apply=True).run()
    saved = await repo.get_by_id(generation.id)
    assert report["copied"] == 1
    assert saved.original_object_key == f"generations/{generation.id}/original.png"
    assert f"generations/{generation.id}/original.png" in storage.objects


@pytest.mark.unit
async def test_resultado_ja_processado_fica_unavailable() -> None:
    repo = InMemoryGenerationRepository()
    storage = InMemoryObjectStorage()
    generation = _generation()
    await repo.save(generation)
    storage.objects[generation.result_object_key] = _png(metadata=True)

    report = await BackfillOriginalsService(generations=repo, storage=storage, apply=True).run()
    saved = await repo.get_by_id(generation.id)
    assert report["unavailable"] == 1
    assert saved.original_object_key is None


@pytest.mark.unit
async def test_dry_run_nao_escreve() -> None:
    repo = InMemoryGenerationRepository()
    storage = InMemoryObjectStorage()
    generation = _generation()
    await repo.save(generation)
    storage.objects[generation.result_object_key] = _png(metadata=False)

    report = await BackfillOriginalsService(generations=repo, storage=storage, apply=False).run()
    assert report["copied"] == 1
    assert report["dry_run"] is True
    assert f"generations/{generation.id}/original.png" not in storage.objects
