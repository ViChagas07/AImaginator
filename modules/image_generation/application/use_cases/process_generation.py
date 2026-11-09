"""Caso de uso executado pelo WORKER (Celery): processa a geracao.

Fluxo: QUEUED -> PROCESSING -> DONE/FAILED, publicando progresso no
Redis Pub/Sub a cada passo (o endpoint SSE do apps/api apenas repassa —
assim qualquer replica da API serve o stream, spec secao 13).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports import (
    EventPublisherPort,
    GenerationRepositoryPort,
    ImageAgentPort,
    ObjectStoragePort,
    stream_channel,
)
from modules.image_generation.application.schemas import GenerationProgressEvent
from modules.image_generation.application.services.moderation import ModerationService
from modules.image_generation.domain.entities import (
    Generation,
    GenerationStatus,
)
from modules.image_generation.domain.moderation import (
    ModerationCategory,
    ModerationLayer,
)
from modules.observability.metrics import (
    CREDITS_REFUNDED_TOTAL,
    ENGINE_FAILURES_TOTAL,
    GENERATION_DURATION,
    GENERATIONS_TOTAL,
    IMAGE_MODERATION_BLOCKS_TOTAL,
    QUOTA_REFUNDS_TOTAL,
    REFUSALS_TOTAL,
)
from modules.prompt_quota.contracts import PromptQuotaRefundPort
from modules.users.application.credits import CreditLedgerService
from modules.users.contracts import User, UserRepositoryPort
from shared_kernel.errors import AImaginatorError, NotFoundError
from shared_kernel.security_errors import ContentBlockedError, ImageBlockedError

logger = logging.getLogger(__name__)


class ProcessGeneration:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        image_agent: ImageAgentPort,
        events: EventPublisherPort,
        storage: ObjectStoragePort | None = None,
        users: UserRepositoryPort | None = None,
        moderation: ModerationService | None = None,
        quota_refund: PromptQuotaRefundPort | None = None,
        credits: CreditLedgerService | None = None,
        commit: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._generations = generations
        self._agent = image_agent
        self._events = events
        self._storage = storage
        self._users = users
        self._moderation = moderation
        self._quota_refund = quota_refund
        self._credits = credits
        self._commit = commit

    async def _commit_if_available(self) -> None:
        if self._commit is not None:
            await self._commit()

    async def _heartbeat(self, generation: Generation) -> None:
        """Persiste updated_at em transacao curta (visivel ao reconciliador)."""
        generation.updated_at = datetime.now(UTC)
        await self._generations.save(generation)
        await self._commit_if_available()

    async def execute(self, generation_id: UUID, *, raise_on_failure: bool = True) -> None:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError(f"Geracao {generation_id} nao encontrada.")
        if generation.status in (GenerationStatus.DONE, GenerationStatus.FAILED):
            # Reentrega idempotente (acks_late): estado terminal sai sem trabalho.
            logger.info(
                "generation_already_terminal",
                extra={
                    "generation_id": str(generation.id),
                    "status": generation.status.value,
                },
            )
            return

        async def publish(status: GenerationStatus, progress: int, **kwargs) -> None:
            await self._events.publish_progress(
                GenerationProgressEvent(
                    generation_id=generation.id,
                    status=status,
                    progress=progress,
                    **kwargs,
                )
            )

        started = time.monotonic()
        try:
            if generation.status is GenerationStatus.PROCESSING:
                # Reentrega apos perda do worker: retoma em vez de transicionar
                # PROCESSING -> PROCESSING (transicao invalida).
                await self._heartbeat(generation)
            else:
                generation.transition_to(GenerationStatus.PROCESSING)
                await self._generations.save(generation)
                await self._commit_if_available()
            await publish(GenerationStatus.PROCESSING, 5)

            async def on_progress(percent: int) -> None:
                await self._heartbeat(generation)
                await publish(GenerationStatus.PROCESSING, min(max(percent, 5), 99))

            result_url = await self._agent.run_generation(generation, on_progress)
            if self._storage is not None and generation.result_object_key:
                result_url = await self._storage.presigned_get_url(generation.result_object_key)

            generation.attach_result(result_url, object_key=generation.result_object_key)
            await self._generations.save(generation)
            await self._commit_if_available()
            GENERATIONS_TOTAL.labels(kind=generation.kind.value, status="done").inc()
            GENERATION_DURATION.labels(kind=generation.kind.value).observe(
                max(0.0, time.monotonic() - started)
            )
            await publish(
                GenerationStatus.DONE,
                100,
                result_image_url=result_url,
                seed=generation.seed,
                parent_generation_id=generation.parent_generation_id,
            )
        except Exception as exc:
            if isinstance(exc, AImaginatorError):
                error_code = exc.code
                safe_message = exc.message
                if error_code in {
                    "engine_offline",
                    "maintenance",
                    "hardware_busy",
                    "thermal_abort",
                    "resource_abort",
                }:
                    safe_message = message_for(error_code, generation.locale)
            else:
                error_code = "engine_failed"
                safe_message = "Falha no processamento."

            warning_level: int | None = None
            warning_message: str | None = None
            if (
                isinstance(exc, ContentBlockedError | ImageBlockedError)
                and exc.category is not None
            ):
                apply_penalty = isinstance(exc, ContentBlockedError) or exc.penalize
                if isinstance(exc, ImageBlockedError):
                    IMAGE_MODERATION_BLOCKS_TOTAL.labels(
                        category=exc.category, layer=exc.layer
                    ).inc()
                outcome = await self._record_moderation(
                    generation, exc, apply_penalty=apply_penalty
                )
                if outcome is not None:
                    warning_level = outcome.warning_level
                    warning_message = outcome.warning_message

            self._record_failure_metrics(generation, error_code)
            if generation.status is not GenerationStatus.DONE:
                await self._refund_credit(generation, reason=error_code)
                await self._refund_quota(generation, reason=error_code)
            if generation.status in (
                GenerationStatus.QUEUED,
                GenerationStatus.PROCESSING,
            ):
                generation.warning_level = warning_level
                generation.warning_message = warning_message
                generation.transition_to(
                    GenerationStatus.FAILED, error=safe_message, error_code=error_code
                )
                await self._generations.save(generation)
                await self._commit_if_available()
            GENERATIONS_TOTAL.labels(kind=generation.kind.value, status="failed").inc()
            GENERATION_DURATION.labels(kind=generation.kind.value).observe(
                max(0.0, time.monotonic() - started)
            )
            await publish(
                GenerationStatus.FAILED,
                100,
                error=safe_message,
                error_code=error_code,
                warning_level=warning_level,
                warning_message=warning_message,
            )
            if raise_on_failure:
                raise

    async def _record_moderation(self, generation: Generation, exc, *, apply_penalty: bool = True):
        if self._moderation is None or exc.category is None:
            return None
        user: User | None = None
        if generation.user_id is not None and self._users is not None:
            user = await self._users.get_by_id(generation.user_id)
        try:
            category = ModerationCategory(exc.category)
        except ValueError:
            return None
        try:
            return await self._moderation.record_moderation(
                category=category,
                layer=ModerationLayer(exc.layer),
                confidence=exc.confidence,
                locale=generation.locale,
                prompt_text=generation.prompt,
                user=user,
                anonymous_session_id=generation.anonymous_session_id,
                ip_hash=generation.ip_hash,
                apply_penalty=apply_penalty,
            )
        except Exception:
            logger.exception(
                "moderation_record_failed",
                extra={"generation_id": str(generation.id)},
            )
            return None

    async def _refund_credit(self, generation: Generation, *, reason: str = "unknown") -> None:
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
                "credit_refund_failed",
                extra={"generation_id": str(generation.id)},
                exc_info=True,
            )

    async def _refund_quota(self, generation: Generation, *, reason: str = "unknown") -> None:
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
                "quota_refund_failed",
                extra={"generation_id": str(generation.id)},
                exc_info=True,
            )
        generation.quota_refunded = True

    @staticmethod
    def _record_failure_metrics(generation: Generation, code: str) -> None:
        refusal_codes = {
            "content_blocked_nsfw",
            "content_blocked_gore",
            "content_blocked_hate",
            "content_blocked_self_harm",
            "source_image_blocked_nsfw",
            "source_image_blocked_gore",
            "source_image_blocked_hate",
            "source_image_blocked_self_harm",
            "image_blocked_nsfw",
            "image_blocked_gore",
            "image_blocked_hate",
            "image_blocked_self_harm",
            "out_of_scope",
            "prompt_rejected",
            "assistant_unavailable",
        }
        if code in refusal_codes:
            REFUSALS_TOTAL.labels(code=code).inc()
        reasons = {
            "engine_timeout": "timeout",
            "engine_oom": "oom",
            "engine_failed": "failed",
            "insufficient_resources": "insufficient_resources",
        }
        reason = reasons.get(code)
        if reason is not None:
            ENGINE_FAILURES_TOTAL.labels(kind=generation.kind.value, reason=reason).inc()


__all__ = ["ProcessGeneration", "stream_channel"]
