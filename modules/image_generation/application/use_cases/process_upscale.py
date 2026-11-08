"""Processa um job kind=upscale: original privado -> 2x -> marca/metadados."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.image_generation.application.ports import (
    EventPublisherPort,
    GenerationRepositoryPort,
    ObjectStoragePort,
    UpscalerPort,
)
from modules.image_generation.application.ports.image_processing import (
    AiMetadataWriterPort,
    C2PASignerPort,
    ImageWatermarkerPort,
)
from modules.image_generation.application.schemas import GenerationProgressEvent
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from modules.image_generation.domain.image_bytes import (
    inspect_image_bytes,
    validate_image_bytes,
)
from modules.observability.metrics import (
    ENGINE_FAILURES_TOTAL,
    GENERATION_DURATION,
    GENERATIONS_TOTAL,
    UPLOAD_FAILURES_TOTAL,
)
from modules.observability.timing import stage_timer
from modules.prompt_quota.application.ports import PromptQuotaStorePort
from shared_kernel.errors import AImaginatorError, DomainError, NotFoundError

logger = logging.getLogger(__name__)


class ProcessUpscale:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        storage: ObjectStoragePort,
        upscaler: UpscalerPort,
        watermarker: ImageWatermarkerPort | None,
        metadata_writer: AiMetadataWriterPort | None,
        events: EventPublisherPort,
        quota_store: PromptQuotaStorePort | None = None,
        c2pa_signer: C2PASignerPort | None = None,
        commit: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._generations = generations
        self._storage = storage
        self._upscaler = upscaler
        self._watermarker = watermarker
        self._metadata_writer = metadata_writer
        self._events = events
        self._quota_store = quota_store
        self._c2pa = c2pa_signer
        self._commit = commit

    async def _commit_if_available(self) -> None:
        if self._commit is not None:
            await self._commit()

    async def _heartbeat(self, generation: Generation) -> None:
        generation.updated_at = datetime.now(UTC)
        await self._generations.save(generation)
        await self._commit_if_available()

    async def execute(self, generation_id: UUID, *, raise_on_failure: bool = True) -> None:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError("Geracao nao encontrada.")
        if generation.status in (GenerationStatus.DONE, GenerationStatus.FAILED):
            logger.info(
                "generation_already_terminal",
                extra={
                    "generation_id": str(generation.id),
                    "status": generation.status.value,
                },
            )
            return

        async def publish(status: GenerationStatus, progress: int, **kwargs) -> None:
            if status is GenerationStatus.PROCESSING:
                await self._heartbeat(generation)
            await self._events.publish_progress(
                GenerationProgressEvent(
                    generation_id=generation.id,
                    status=status,
                    progress=progress,
                    **kwargs,
                )
            )

        started = time.monotonic()
        saved_original = False
        saved_result = False
        original_key = f"generations/{generation.id}/original.png"
        result_key = f"generations/{generation.id}/result.png"
        try:
            if generation.status is GenerationStatus.PROCESSING:
                await self._heartbeat(generation)
            else:
                generation.transition_to(GenerationStatus.PROCESSING)
                await self._generations.save(generation)
                await self._commit_if_available()
            await publish(GenerationStatus.PROCESSING, 5)

            parent = None
            if generation.parent_generation_id is not None:
                parent = await self._generations.get_by_id(generation.parent_generation_id)
            source_key = generation.source_object_key or (
                parent.original_object_key if parent else None
            )
            if not source_key:
                raise DomainError("Original privado indisponivel para ampliacao.")
            source = await self._storage.get_object(source_key)
            source_meta = inspect_image_bytes(source)
            await publish(GenerationStatus.PROCESSING, 20)

            with stage_timer("upscale", correlation_id=str(generation.id)):
                upscaled = await self._upscaler.upscale(source, factor=2)
            expected_w, expected_h = source_meta.width * 2, source_meta.height * 2
            validate_image_bytes(
                upscaled.image_bytes,
                expected_width=expected_w,
                expected_height=expected_h,
            )
            await publish(GenerationStatus.PROCESSING, 80)

            try:
                await self._storage.put_object(
                    original_key, upscaled.image_bytes, content_type="image/png"
                )
            except Exception:
                UPLOAD_FAILURES_TOTAL.labels(stage="upscale_original").inc()
                raise
            saved_original = True
            generation.original_object_key = original_key
            await publish(GenerationStatus.PROCESSING, 92)

            public_bytes = upscaled.image_bytes
            with stage_timer("watermark_metadata", correlation_id=str(generation.id)):
                if self._watermarker is not None:
                    public_bytes = await asyncio.to_thread(self._watermarker.apply, public_bytes)
                if self._metadata_writer is not None:
                    public_bytes = await asyncio.to_thread(
                        self._metadata_writer.apply,
                        public_bytes,
                        model_name=_model_name(parent),
                    )
                if self._c2pa is not None:
                    public_bytes = await asyncio.to_thread(self._c2pa.sign, public_bytes)
            validate_image_bytes(
                public_bytes, expected_width=expected_w, expected_height=expected_h
            )
            await publish(GenerationStatus.PROCESSING, 98)
            try:
                with stage_timer("upload", correlation_id=str(generation.id)):
                    await self._storage.put_object(
                        result_key, public_bytes, content_type="image/png"
                    )
            except Exception:
                UPLOAD_FAILURES_TOTAL.labels(stage="upscale").inc()
                raise
            saved_result = True

            url = await self._storage.presigned_get_url(result_key)
            generation.result_object_key = result_key
            generation.attach_result(url, object_key=result_key)
            await self._generations.save(generation)
            await self._commit_if_available()
            GENERATIONS_TOTAL.labels(kind="upscale", status="done").inc()
            GENERATION_DURATION.labels(kind="upscale").observe(max(0.0, time.monotonic() - started))
            await publish(
                GenerationStatus.DONE,
                100,
                result_image_url=url,
                parent_generation_id=generation.parent_generation_id,
            )
        except Exception as exc:
            if saved_result:
                await _safe_delete(self._storage, result_key)
            if saved_original:
                await _safe_delete(self._storage, original_key)
                generation.original_object_key = None
            code = exc.code if isinstance(exc, AImaginatorError) else "engine_failed"
            message = (
                exc.message if isinstance(exc, AImaginatorError) else "Falha ao ampliar a imagem."
            )
            if code in {
                "engine_timeout",
                "engine_oom",
                "engine_failed",
                "insufficient_resources",
            }:
                reason = code.removeprefix("engine_")
                if reason == "insufficient_resources":
                    reason = "insufficient_resources"
                ENGINE_FAILURES_TOTAL.labels(kind="upscale", reason=reason).inc()
            await self._release_slot(generation)
            GENERATIONS_TOTAL.labels(kind="upscale", status="failed").inc()
            GENERATION_DURATION.labels(kind="upscale").observe(max(0.0, time.monotonic() - started))
            if generation.status in (
                GenerationStatus.QUEUED,
                GenerationStatus.PROCESSING,
            ):
                generation.transition_to(GenerationStatus.FAILED, error=message, error_code=code)
                await self._generations.save(generation)
                await self._commit_if_available()
            await publish(GenerationStatus.FAILED, 100, error=message, error_code=code)
            if raise_on_failure:
                raise

    async def _release_slot(self, generation: Generation) -> None:
        if self._quota_store is None or generation.user_id is None or generation.upscale_refunded:
            return
        try:
            await self._quota_store.release(principal_id=f"user:{generation.user_id}")
            generation.upscale_refunded = True
        except Exception:
            logger.warning(
                "upscale_limit_refund_failed",
                extra={"generation_id": str(generation.id)},
                exc_info=True,
            )


def _model_name(parent: Generation | None) -> str:
    if parent is not None and parent.kind is GenerationKind.EDIT:
        return "FLUX.1 Kontext"
    return "FLUX.1 Dev"


async def _safe_delete(storage: ObjectStoragePort, key: str) -> None:
    try:
        await storage.delete_object(key)
    except Exception:
        logger.warning("asset_cleanup_failed", extra={"key": key}, exc_info=True)
