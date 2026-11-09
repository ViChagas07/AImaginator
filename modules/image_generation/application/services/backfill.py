"""Backfill idempotente de originais privados (sem prompt em log)."""

from __future__ import annotations

import io

from PIL import Image

from modules.image_generation.application.ports.event_publisher import EventPublisherPort
from modules.image_generation.application.ports.generation_repository import (
    GenerationRepositoryPort,
)
from modules.image_generation.application.ports.object_storage import ObjectStoragePort
from modules.observability.logging_config import get_logger

logger = get_logger(__name__)


def has_postprocess_metadata(image_bytes: bytes) -> bool:
    """Metadados de IA indicam que o result ja passou por marca/pos-processo."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            info = image.info or {}
            keys = {str(key).lower() for key in info}
            text = " ".join(str(value) for value in info.values()).lower()
            return "digitalsourcetype" in keys or "generator" in keys or "aimaginator" in text
    except Exception:
        return True


class BackfillOriginalsService:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        storage: ObjectStoragePort,
        events: EventPublisherPort | None = None,
        apply: bool = False,
    ) -> None:
        self._generations = generations
        self._storage = storage
        self._events = events
        self._apply = apply

    async def run(self, *, limit: int = 500) -> dict:
        report = {"copied": 0, "unavailable": 0, "skipped": 0, "dry_run": not self._apply}
        for generation in await self._generations.list_done_without_original(limit=limit):
            if generation.result_object_key is None:
                report["skipped"] += 1
                continue
            try:
                data = await self._storage.get_object(generation.result_object_key)
            except Exception:
                report["unavailable"] += 1
                continue
            if has_postprocess_metadata(data):
                report["unavailable"] += 1
                continue
            if not self._apply:
                report["copied"] += 1
                continue
            key = f"generations/{generation.id}/original.png"
            await self._storage.put_object(key, data, content_type="image/png")
            generation.original_object_key = key
            await self._generations.save(generation)
            report["copied"] += 1
        logger.info("backfill_originals_done", **report)
        return report
