"""Cancelamento de geracao (fila ou processamento)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports import EventPublisherPort, GenerationRepositoryPort
from modules.image_generation.application.schemas import GenerationProgressEvent
from modules.image_generation.domain.entities import GenerationStatus
from modules.observability.logging_config import get_logger
from modules.prompt_quota.contracts import PromptQuotaRefundPort
from modules.users.application.credits import CreditLedgerService
from shared_kernel.errors import ForbiddenError, NotFoundError

logger = get_logger(__name__)


class CancelGeneration:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        events: EventPublisherPort,
        redis,
        credits: CreditLedgerService | None = None,
        quota_refund: PromptQuotaRefundPort | None = None,
    ) -> None:
        self._generations = generations
        self._events = events
        self._redis = redis
        self._credits = credits
        self._quota_refund = quota_refund

    async def execute(
        self,
        *,
        user_id: UUID | None,
        anonymous_session_id: str | None = None,
        generation_id: UUID,
    ) -> dict:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError("Geracao nao encontrada.")
        if not generation.belongs_to(
            user_id, anonymous_session_id=anonymous_session_id
        ):
            raise ForbiddenError("Acesso negado a esta geracao.")
        if generation.status in (
            GenerationStatus.DONE,
            GenerationStatus.FAILED,
            GenerationStatus.CANCELED,
        ):
            return {
                "id": str(generation.id),
                "status": generation.status.value,
                "canceled": False,
                "already_finished": True,
            }

        # Sinaliza o worker mesmo quando o CAS abaixo perder a corrida.
        await self._redis.setex(f"cancel:{generation.id}", 3600, "1")
        if generation.status is not GenerationStatus.QUEUED:
            return {
                "id": str(generation.id),
                "status": "cancel_requested",
                "canceled": False,
            }

        message = message_for("canceled", generation.locale)
        now = datetime.now(UTC)
        changed = await self._transition_if_status(
            generation,
            from_statuses=(GenerationStatus.QUEUED,),
            to_status=GenerationStatus.CANCELED,
            error_message=message,
            error_code="canceled",
            completed_at=now,
            updated_at=now,
        )
        if not changed:
            current = await self._generations.get_by_id(generation.id)
            if current is None:
                raise NotFoundError("Geracao nao encontrada.")
            if current.status is GenerationStatus.PROCESSING:
                return {
                    "id": str(current.id),
                    "status": "cancel_requested",
                    "canceled": False,
                }
            return {
                "id": str(current.id),
                "status": current.status.value,
                "canceled": False,
                "already_finished": True,
            }

        generation.transition_to(
            GenerationStatus.CANCELED, error=message, error_code="canceled"
        )
        await self._refund(generation)
        # Persiste os flags de refund no estado terminal CANCELED.
        await self._generations.save(generation)
        await self._events.publish_progress(
            GenerationProgressEvent(
                generation_id=generation.id,
                status=GenerationStatus.CANCELED,
                progress=100,
                error=message,
                error_code="canceled",
            )
        )
        logger.info("generation_canceled", correlation_id=str(generation.id))
        return {"id": str(generation.id), "status": "canceled", "canceled": True}

    async def _transition_if_status(
        self,
        generation,
        *,
        from_statuses,
        to_status,
        **values,
    ) -> bool:
        transition = getattr(self._generations, "transition_if_status", None)
        if transition is None:
            # Compatibilidade com fakes antigos; o repositorio real usa CAS.
            # A transicao/save terminal e feita pelo chamador apos o CAS.
            if generation.status not in from_statuses:
                return False
            for key, value in values.items():
                if hasattr(generation, key):
                    setattr(generation, key, value)
            return True
        return await transition(
            generation.id,
            from_statuses=from_statuses,
            to_status=to_status,
            **values,
        )

    async def _refund(self, generation) -> None:
        if generation.credits_refunded or generation.quota_refunded:
            return
        if self._credits is not None and generation.user_id is not None:
            try:
                await self._credits.refund(
                    generation.user_id,
                    amount=generation.credits_cost,
                    ref_type="generation",
                    ref_id=str(generation.id),
                    idempotency_key=f"refund:{generation.id}",
                    meta={"reason": "canceled"},
                )
                generation.credits_refunded = True
            except Exception:
                logger.warning("cancel_credit_refund_failed", exc_info=True)
        if self._quota_refund is not None:
            if generation.user_id is not None:
                principal = f"user:{generation.user_id}"
            elif generation.anonymous_session_id:
                principal = f"anon:{generation.anonymous_session_id}"
            else:
                principal = None
            if principal:
                try:
                    await self._quota_refund.refund(principal)
                except Exception:
                    logger.warning("cancel_quota_refund_failed", exc_info=True)
                generation.quota_refunded = True
