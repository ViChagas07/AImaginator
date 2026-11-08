"""Cria uma ampliacao 2x de uma geracao concluida (limite diario proprio)."""

from __future__ import annotations

from uuid import UUID

from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports import (
    EventPublisherPort,
    GenerationRepositoryPort,
    TaskQueuePort,
)
from modules.image_generation.application.schemas import (
    GenerationOutput,
    GenerationProgressEvent,
)
from modules.image_generation.application.services.queue_recovery import (
    QueueRecoveryService,
)
from modules.image_generation.application.use_cases.generate_image import _to_output
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from modules.observability.logging_config import get_logger
from modules.observability.metrics import UPSCALE_LIMIT_HITS_TOTAL
from modules.prompt_quota.application.ports import PromptQuotaStorePort
from modules.prompt_quota.contracts import RefundPromptQuota
from modules.users.contracts import User
from shared_kernel.errors import DomainError, ForbiddenError, NotFoundError
from shared_kernel.security_errors import (
    OriginalUnavailableError,
    QueuePublishFailedError,
    UpscaleLimitExceededError,
)

logger = get_logger(__name__)


class CreateUpscale:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        task_queue: TaskQueuePort,
        quota_store: PromptQuotaStorePort,
        daily_limit: int,
        events: EventPublisherPort | None = None,
    ) -> None:
        self._generations = generations
        self._queue = task_queue
        self._quota_store = quota_store
        self._daily_limit = daily_limit
        self._events = events

    async def execute(
        self,
        *,
        generation_id: UUID,
        user: User,
        locale: str = "pt-BR",
        ip_hash: str | None = None,
    ) -> GenerationOutput:
        parent = await self._generations.get_by_id(generation_id)
        if parent is None:
            raise NotFoundError("Geracao nao encontrada.")
        if parent.user_id != user.id:
            raise ForbiddenError("Acesso negado a esta geracao.")
        if parent.status is not GenerationStatus.DONE:
            raise DomainError("A geracao ainda nao esta pronta para ampliacao.")
        if not parent.original_object_key:
            raise OriginalUnavailableError(message_for("original_unavailable", locale))

        try:
            quota = await self._quota_store.consume(
                principal_id=f"user:{user.id}", total=self._daily_limit
            )
        except Exception as exc:
            if getattr(exc, "code", None) == "quota_exceeded":
                retry_after = max(1, int(getattr(exc, "retry_after_seconds", 0) or 0))
                UPSCALE_LIMIT_HITS_TOTAL.inc()
                raise UpscaleLimitExceededError(
                    message_for("upscale_limit_reached", locale),
                    retry_after_seconds=retry_after,
                ) from exc
            raise

        generation = Generation(
            user_id=user.id,
            kind=GenerationKind.UPSCALE,
            prompt=parent.prompt,
            aspect_ratio=parent.aspect_ratio,
            source_object_key=parent.original_object_key,
            parent_generation_id=parent.id,
            locale=locale,
            ip_hash=ip_hash,
        )
        try:
            await self._generations.save(generation)
        except Exception:
            await self._quota_store.release(principal_id=f"user:{user.id}")
            raise
        try:
            self._queue.enqueue_generation(generation.id, kind=generation.kind.value)
        except Exception as exc:
            logger.warning(
                "queue_publish_failed",
                correlation_id=str(generation.id),
                error_type=type(exc).__name__,
            )
            await QueueRecoveryService(
                generations=self._generations,
                events=self._events,
                quota_refund=RefundPromptQuota(self._quota_store),
            ).mark_publish_failed(generation)
            raise QueuePublishFailedError(message_for("queue_publish_failed", locale)) from exc

        logger.info(
            "generation_created",
            correlation_id=str(generation.id),
            kind=generation.kind.value,
            locale=locale,
        )
        if self._events is not None:
            await self._events.publish_progress(
                GenerationProgressEvent(
                    generation_id=generation.id,
                    status=GenerationStatus.QUEUED,
                    progress=0,
                )
            )
        output = _to_output(generation)
        output.upscale_remaining = quota.chances_remaining
        return output
