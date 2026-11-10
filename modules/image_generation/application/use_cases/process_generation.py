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
from modules.image_generation.application.ports.llm_client import (
    LlmTimeoutError,
    LlmUnavailableError,
)
from modules.image_generation.application.schemas import GenerationProgressEvent
from modules.image_generation.application.services.moderation import ModerationService
from modules.image_generation.domain.engine_errors import EngineFailedError
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
from shared_kernel.errors import (
    AImaginatorError,
    DomainError,
    GenerationFinalizationError,
    NotFoundError,
)
from shared_kernel.security_errors import (
    AssistantUnavailableError,
    ContentBlockedError,
    GenerationCanceledError,
    ImageBlockedError,
)

logger = logging.getLogger(__name__)

# Falhas transitorias que podem reexecutar o pipeline ANTES do motor.
_TRANSIENT_PRE_ENGINE_ERRORS = (
    ConnectionError,
    TimeoutError,
    LlmTimeoutError,
    LlmUnavailableError,
    AssistantUnavailableError,
)


def _stage_for_progress(status: GenerationStatus, progress: int) -> str:
    if status is GenerationStatus.PROCESSING:
        if progress <= 10:
            return "assistant"
        if progress < 90:
            return "engine"
        if progress < 99:
            return "finalizing"
        return "upload"
    if status is GenerationStatus.DONE:
        return "done"
    if status is GenerationStatus.CANCELED:
        return "canceled"
    if status is GenerationStatus.FAILED:
        return "failed"
    return "queued"


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
        rollback: Callable[[], Awaitable[None]] | None = None,
        cancel_check: Callable[[], Awaitable[bool]] | None = None,
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
        self._rollback = rollback
        self._cancel_check = cancel_check

    async def _commit_if_available(self) -> None:
        if self._commit is not None:
            await self._commit()

    async def _rollback_if_available(self) -> None:
        if self._rollback is not None:
            await self._rollback()

    async def _heartbeat(self, generation: Generation) -> None:
        """Persiste updated_at em transacao curta (visivel ao reconciliador)."""
        generation.updated_at = datetime.now(UTC)
        touch = getattr(self._generations, "touch_processing", None)
        if touch is None:
            await self._generations.save(generation)
        else:
            still_processing = await touch(
                generation.id, updated_at=generation.updated_at
            )
            if not still_processing:
                current = await self._generations.get_by_id(generation.id)
                if current is not None and current.status is GenerationStatus.CANCELED:
                    raise GenerationCanceledError(
                        message_for("canceled", generation.locale)
                    )
                raise DomainError("Geracao nao esta mais em processamento.")
        await self._commit_if_available()

    async def _transition(
        self,
        generation: Generation,
        *,
        from_statuses,
        to_status: GenerationStatus,
        **values,
    ) -> bool:
        transition = getattr(self._generations, "transition_if_status", None)
        if transition is None:
            # Compatibilidade com fakes antigos; o repositorio real usa CAS.
            if generation.status not in from_statuses:
                return False
            for key, value in values.items():
                if hasattr(generation, key):
                    setattr(generation, key, value)
            generation.transition_to(
                to_status,
                error=values.get("error_message"),
                error_code=values.get("error_code"),
            )
            await self._generations.save(generation)
            return True
        return await transition(
            generation.id,
            from_statuses=from_statuses,
            to_status=to_status,
            **values,
        )

    async def _discard_result(self, generation: Generation) -> None:
        if self._storage is None:
            return
        for key in (generation.result_object_key, generation.original_object_key):
            if not key:
                continue
            try:
                await self._storage.delete_object(key)
            except Exception:
                logger.warning(
                    "canceled_result_delete_failed",
                    extra={"generation_id": str(generation.id), "key": key},
                    exc_info=True,
                )

    @staticmethod
    async def _publish_terminal(publish, status: GenerationStatus, **kwargs) -> None:
        """Evento terminal e best-effort: nunca derruba a task por Redis."""
        try:
            await publish(status, 100, **kwargs)
        except Exception:
            logger.warning(
                "generation_terminal_publish_failed",
                extra={"status": status.value},
                exc_info=True,
            )

    async def _finalize_failed(
        self,
        generation: Generation,
        *,
        from_statuses,
        publish,
        reason: str,
    ) -> bool:
        """Fallback: FAILED com refund unico depois do commit do estado."""
        message = EngineFailedError().message
        try:
            changed = await self._transition(
                generation,
                from_statuses=from_statuses,
                to_status=GenerationStatus.FAILED,
                error_message=message,
                error_code="finalize_failed",
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                result_image_url=None,
                result_object_key=None,
                original_object_key=None,
            )
            if changed:
                # Estado terminal persistido antes de qualquer refund.
                await self._commit_if_available()
        except Exception:
            logger.exception(
                "generation_finalize_fallback_failed",
                extra={"generation_id": str(generation.id), "reason": reason},
            )
            raise GenerationFinalizationError(
                "Falha ao finalizar a geracao."
            ) from None

        if not changed:
            return False

        generation.status = GenerationStatus.FAILED
        generation.error_message = message
        generation.error_code = "finalize_failed"
        generation.completed_at = datetime.now(UTC)
        generation.updated_at = datetime.now(UTC)
        generation.result_image_url = None
        generation.result_object_key = None
        generation.original_object_key = None
        await self._refund_credit(generation, reason="finalize_failed")
        await self._refund_quota(generation, reason="finalize_failed")
        try:
            await self._generations.save(generation)
            await self._commit_if_available()
        except Exception:
            logger.warning(
                "generation_finalize_refund_persist_failed",
                extra={"generation_id": str(generation.id)},
                exc_info=True,
            )
        await self._publish_terminal(
            publish,
            GenerationStatus.FAILED,
            error=message,
            error_code="finalize_failed",
        )
        return True

    async def _finalize_terminal(
        self,
        generation: Generation,
        *,
        from_statuses,
        to_status: GenerationStatus,
        publish,
        event_kwargs: dict | None = None,
        **values,
    ) -> GenerationStatus | None:
        """CAS terminal + commit + refund + evento; fallback FAILED em erro."""
        if to_status in (GenerationStatus.FAILED, GenerationStatus.CANCELED):
            values.setdefault("result_image_url", None)
            values.setdefault("result_object_key", None)
            values.setdefault("original_object_key", None)
        try:
            changed = await self._transition(
                generation,
                from_statuses=from_statuses,
                to_status=to_status,
                **values,
            )
        except Exception:
            logger.exception(
                "generation_finalize_failed",
                extra={
                    "generation_id": str(generation.id),
                    "to_status": to_status.value,
                },
            )
            await self._rollback_if_available()
            fallback = await self._finalize_failed(
                generation,
                from_statuses=from_statuses,
                publish=publish,
                reason=to_status.value,
            )
            return GenerationStatus.FAILED if fallback else None

        if not changed:
            return None

        # Estado terminal sempre commitado antes de refund/evento.
        await self._commit_if_available()
        for key in (
            "result_image_url",
            "result_object_key",
            "original_object_key",
            "seed",
            "error_message",
            "error_code",
            "warning_level",
            "warning_message",
            "completed_at",
            "updated_at",
        ):
            if key in values:
                setattr(generation, key, values[key])
        generation.status = to_status
        if generation.completed_at is None:
            generation.completed_at = datetime.now(UTC)
        if to_status in (GenerationStatus.FAILED, GenerationStatus.CANCELED):
            reason = values.get("error_code") or "unknown"
            await self._refund_credit(generation, reason=reason)
            await self._refund_quota(generation, reason=reason)
            try:
                await self._generations.save(generation)
                await self._commit_if_available()
            except Exception:
                logger.warning(
                    "generation_finalize_refund_persist_failed",
                    extra={"generation_id": str(generation.id)},
                    exc_info=True,
                )
        await self._publish_terminal(
            publish, to_status, **(event_kwargs or {})
        )
        return to_status

    async def execute(
        self, generation_id: UUID, *, raise_on_failure: bool = True
    ) -> None:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError(f"Geracao {generation_id} nao encontrada.")
        if generation.status in (
            GenerationStatus.DONE,
            GenerationStatus.FAILED,
            GenerationStatus.CANCELED,
        ):
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
            stage = kwargs.pop("stage", None) or _stage_for_progress(
                status, progress
            )
            logger.info(
                "generation_progress_published",
                extra={
                    "generation_id": str(generation.id),
                    "status": status.value,
                    "stage": stage,
                    "progress": progress,
                    "ts": time.time(),
                },
            )
            await self._events.publish_progress(
                GenerationProgressEvent(
                    generation_id=generation.id,
                    status=status,
                    progress=progress,
                    stage=stage,
                    **kwargs,
                )
            )

        started = time.monotonic()

        # A flag e checada no inicio de cada tentativa, antes do assistente.
        if self._cancel_check is not None and await self._cancel_check():
            message = message_for("canceled", generation.locale)
            effective = await self._finalize_terminal(
                generation,
                from_statuses=(GenerationStatus.QUEUED, GenerationStatus.PROCESSING),
                to_status=GenerationStatus.CANCELED,
                publish=publish,
                error_message=message,
                error_code="canceled",
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                event_kwargs={"error": message, "error_code": "canceled"},
            )
            if effective is GenerationStatus.CANCELED:
                GENERATIONS_TOTAL.labels(
                    kind=generation.kind.value, status="canceled"
                ).inc()
                GENERATION_DURATION.labels(kind=generation.kind.value).observe(
                    max(0.0, time.monotonic() - started)
                )
            return

        engine_started = False
        try:
            if generation.status is GenerationStatus.PROCESSING:
                # Reentrega apos perda do worker: retoma em vez de transicionar
                # PROCESSING -> PROCESSING (transicao invalida).
                await self._heartbeat(generation)
            else:
                changed = await self._transition(
                    generation,
                    from_statuses=(GenerationStatus.QUEUED,),
                    to_status=GenerationStatus.PROCESSING,
                    updated_at=datetime.now(UTC),
                )
                if not changed:
                    current = await self._generations.get_by_id(generation.id)
                    if current is None:
                        raise NotFoundError(
                            f"Geracao {generation_id} nao encontrada."
                        )
                    if current.status in (
                        GenerationStatus.DONE,
                        GenerationStatus.FAILED,
                        GenerationStatus.CANCELED,
                    ):
                        logger.info(
                            "generation_already_terminal",
                            extra={
                                "generation_id": str(current.id),
                                "status": current.status.value,
                            },
                        )
                        return
                    generation = current
                else:
                    generation.status = GenerationStatus.PROCESSING
                await self._commit_if_available()
            await publish(GenerationStatus.PROCESSING, 5)

            async def on_progress(percent: int) -> None:
                nonlocal engine_started
                if percent > 10:
                    engine_started = True
                await self._heartbeat(generation)
                await publish(GenerationStatus.PROCESSING, min(max(percent, 5), 99))

            result_url = await self._agent.run_generation(generation, on_progress)
            if self._cancel_check is not None and await self._cancel_check():
                raise GenerationCanceledError(
                    message_for("canceled", generation.locale)
                )
            if self._storage is not None and generation.result_object_key:
                result_url = await self._storage.presigned_get_url(generation.result_object_key)

            completed = await self._finalize_terminal(
                generation,
                from_statuses=(GenerationStatus.PROCESSING,),
                to_status=GenerationStatus.DONE,
                publish=publish,
                result_image_url=result_url,
                result_object_key=generation.result_object_key,
                seed=generation.seed,
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                event_kwargs={
                    "result_image_url": result_url,
                    "seed": generation.seed,
                    "parent_generation_id": generation.parent_generation_id,
                },
            )
            if completed is not GenerationStatus.DONE:
                return
            GENERATIONS_TOTAL.labels(kind=generation.kind.value, status="done").inc()
            GENERATION_DURATION.labels(kind=generation.kind.value).observe(
                max(0.0, time.monotonic() - started)
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
                    "canceled",
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

            final_status = (
                GenerationStatus.CANCELED
                if error_code == "canceled"
                else GenerationStatus.FAILED
            )

            # Falhas transitorias ANTES do motor podem reexecutar o pipeline;
            # depois do motor, nunca reexecuta o sd-cli.
            if not engine_started and isinstance(exc, _TRANSIENT_PRE_ENGINE_ERRORS):
                raise

            await self._discard_result(generation)
            effective = await self._finalize_terminal(
                generation,
                from_statuses=(
                    GenerationStatus.QUEUED,
                    GenerationStatus.PROCESSING,
                ),
                to_status=final_status,
                publish=publish,
                error_message=safe_message,
                error_code=error_code,
                warning_level=warning_level,
                warning_message=warning_message,
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                event_kwargs={
                    "error": safe_message,
                    "error_code": error_code,
                    "warning_level": warning_level,
                    "warning_message": warning_message,
                },
            )
            if effective is None:
                # Outro caminho ja venceu (DONE/CANCELED/FAILED): nao
                # devolve cota de novo e nao publica um estado duplicado.
                logger.info(
                    "generation_terminal_race_lost",
                    extra={
                        "generation_id": str(generation.id),
                        "error_code": error_code,
                    },
                )
                return

            effective_code = (
                error_code if effective is final_status else "finalize_failed"
            )
            self._record_failure_metrics(generation, effective_code)
            GENERATIONS_TOTAL.labels(
                kind=generation.kind.value, status=effective.value
            ).inc()
            GENERATION_DURATION.labels(kind=generation.kind.value).observe(
                max(0.0, time.monotonic() - started)
            )

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
