"""Recuperacao de fila: publish que falhou e geracoes orfas.

Duas garantias:
- enqueue que falha nunca deixa a Generation em queued;
- queued/processing sem heartbeat por QUEUE_STALE_SECONDS vira queue_lost,
  com refund idempotente de credito/cota e evento SSE.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports.event_publisher import EventPublisherPort
from modules.image_generation.application.ports.generation_repository import (
    GenerationRepositoryPort,
)
from modules.image_generation.application.schemas import GenerationProgressEvent
from modules.image_generation.domain.entities import Generation, GenerationStatus
from modules.observability.logging_config import get_logger
from modules.observability.metrics import (
    CREDITS_REFUNDED_TOTAL,
    QUEUE_RECONCILED_TOTAL,
    QUOTA_REFUNDS_TOTAL,
)
from modules.prompt_quota.contracts import PromptQuotaRefundPort
from modules.users.application.credits import CreditLedgerService
from modules.users.contracts import UserRepositoryPort
from shared_kernel.errors import DomainError

logger = get_logger(__name__)

_TERMINAL = (GenerationStatus.DONE, GenerationStatus.FAILED)
_STALE_STATUSES = (GenerationStatus.QUEUED, GenerationStatus.PROCESSING)


class QueueRecoveryService:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        events: EventPublisherPort | None = None,
        users: UserRepositoryPort | None = None,
        quota_refund: PromptQuotaRefundPort | None = None,
        credits: CreditLedgerService | None = None,
        stale_seconds: int = 900,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._generations = generations
        self._events = events
        self._users = users
        self._quota_refund = quota_refund
        self._credits = credits
        self._stale_seconds = stale_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    def _cutoff(self) -> datetime:
        return self._clock() - timedelta(seconds=self._stale_seconds)

    async def mark_publish_failed(self, generation: Generation) -> bool:
        """Marca FAILED quando o publish no broker falhou."""
        return await self._fail(generation, code="queue_publish_failed")

    async def reconcile_all(self, *, limit: int = 100) -> int:
        cutoff = self._cutoff()
        stale = await self._generations.list_stale(older_than=cutoff, limit=limit)
        return await self._fail_many(stale, code="queue_lost", cutoff=cutoff)

    async def reconcile_user(self, user_id: UUID, *, limit: int = 100) -> int:
        cutoff = self._cutoff()
        stale = await self._generations.list_stale_for_user(user_id, older_than=cutoff, limit=limit)
        return await self._fail_many(stale, code="queue_lost", cutoff=cutoff)

    async def reconcile_generation(self, generation_id: UUID) -> bool:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            return False
        if generation.status not in _STALE_STATUSES:
            return False
        if generation.updated_at >= self._cutoff():
            return False
        return await self._fail(generation, code="queue_lost")

    async def _fail_many(self, stale: list[Generation], *, code: str, cutoff: datetime) -> int:
        reconciled = 0
        for generation in stale:
            if generation.status not in _STALE_STATUSES:
                continue
            if generation.updated_at >= cutoff:
                continue
            if await self._fail(generation, code=code):
                reconciled += 1
        return reconciled

    async def _fail(self, generation: Generation, *, code: str) -> bool:
        if generation.status in _TERMINAL:
            return False
        message = message_for(code, generation.locale)
        try:
            generation.transition_to(GenerationStatus.FAILED, error=message, error_code=code)
        except DomainError:
            logger.warning(
                "queue_reconcile_transition_failed",
                generation_id=str(generation.id),
                status=generation.status.value,
            )
            return False
        generation.updated_at = self._clock()
        generation.error_message = message
        generation.error_code = code

        await self._refund_credit(generation, reason=code)
        await self._refund_quota(generation, reason=code)
        await self._generations.save(generation)

        if self._events is not None:
            try:
                await self._events.publish_progress(
                    GenerationProgressEvent(
                        generation_id=generation.id,
                        status=GenerationStatus.FAILED,
                        progress=100,
                        error=message,
                        error_code=code,
                    )
                )
            except Exception:
                logger.warning(
                    "queue_reconcile_publish_failed",
                    generation_id=str(generation.id),
                    exc_info=True,
                )
        QUEUE_RECONCILED_TOTAL.labels(code=code).inc()
        logger.warning(
            "queue_generation_reconciled",
            generation_id=str(generation.id),
            code=code,
            kind=generation.kind.value,
        )
        return True

    async def _refund_credit(self, generation: Generation, *, reason: str) -> None:
        if self._users is None or generation.user_id is None or generation.credits_refunded:
            return
        try:
            if self._credits is not None:
                await self._credits.refund(
                    generation.user_id,
                    amount=generation.credits_cost,
                    ref_type="generation",
                    ref_id=str(generation.id),
                    idempotency_key=f"refund:{generation.id}",
                    meta={"reason": reason},
                )
                generation.credits_refunded = True
                CREDITS_REFUNDED_TOTAL.labels(reason=reason).inc()
                return
            user = await self._users.get_by_id(generation.user_id)
            if user is None:
                return
            user.generation_credits += generation.credits_cost
            await self._users.save(user)
            generation.credits_refunded = True
            CREDITS_REFUNDED_TOTAL.labels(reason=reason).inc()
        except Exception:
            logger.warning(
                "queue_credit_refund_failed",
                generation_id=str(generation.id),
                exc_info=True,
            )

    async def _refund_quota(self, generation: Generation, *, reason: str) -> None:
        if self._quota_refund is None or generation.quota_refunded:
            return
        if generation.user_id is not None:
            principal = f"user:{generation.user_id}"
        elif generation.anonymous_session_id:
            principal = f"anon:{generation.anonymous_session_id}"
        else:
            return
        try:
            refunded = await self._quota_refund.refund(principal)
            if refunded:
                QUOTA_REFUNDS_TOTAL.labels(reason=reason).inc()
        except Exception:
            logger.warning(
                "queue_quota_refund_failed",
                generation_id=str(generation.id),
                exc_info=True,
            )
        generation.quota_refunded = True
