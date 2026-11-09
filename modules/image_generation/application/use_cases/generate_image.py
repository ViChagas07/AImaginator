"""Caso de uso: gerar imagem nova a partir de prompt (spec: GenerateImageFromPrompt)."""

from __future__ import annotations

from modules.image_generation.application.guardrails import (
    check_scope_localized,
    validate_prompt_localized,
)
from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports import (
    EventPublisherPort,
    GenerationRepositoryPort,
    TaskQueuePort,
)
from modules.image_generation.application.schemas import (
    GenerateImageInput,
    GenerationOutput,
    GenerationProgressEvent,
)
from modules.image_generation.application.services.queue_recovery import (
    QueueRecoveryService,
)
from modules.image_generation.domain.entities import Generation, GenerationKind, GenerationStatus
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.prompt_topic_guard import IPromptTopicGuard
from modules.image_generation.domain.scope_guard import ScopeGuardrail
from modules.observability.logging_config import get_logger
from modules.prompt_quota.contracts import (
    PromptQuotaConsumerPort,
    PromptQuotaRefundPort,
)
from modules.users.application.credits import CreditLedgerService
from modules.users.contracts import User, UserRepositoryPort
from shared_kernel.errors import QuotaExceededError
from shared_kernel.security_errors import QueuePublishFailedError

_STREAM_PATH = "/api/v1/generations/{id}/stream"


def _to_output(generation: Generation) -> GenerationOutput:
    output = GenerationOutput(
        id=generation.id,
        kind=generation.kind,
        status=generation.status,
        prompt=generation.prompt,
        style_preset=generation.style_preset,
        aspect_ratio=generation.aspect_ratio,
        title=generation.title,
        seed=generation.seed,
        parent_generation_id=generation.parent_generation_id,
        result_image_url=generation.result_image_url,
        error_message=generation.error_message,
        created_at=generation.created_at,
        completed_at=generation.completed_at,
    )
    output.stream_url = _STREAM_PATH.format(id=generation.id)
    return output


logger = get_logger(__name__)


class GenerateImageFromPrompt:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        users: UserRepositoryPort,
        task_queue: TaskQueuePort,
        prompt_guard: PromptInjectionGuard,
        topic_guard: IPromptTopicGuard | None = None,
        events: EventPublisherPort | None = None,
        prompt_quota: PromptQuotaConsumerPort | None = None,
        quota_refund: PromptQuotaRefundPort | None = None,
        credits: CreditLedgerService | None = None,
        scope_guardrail: ScopeGuardrail | None = None,
    ) -> None:
        self._generations = generations
        self._users = users
        self._queue = task_queue
        self._guard = prompt_guard
        self._topic_guard = topic_guard
        self._events = events
        self._prompt_quota = prompt_quota
        self._quota_refund = quota_refund
        self._credits = credits
        self._scope_guardrail = scope_guardrail or ScopeGuardrail()

    async def _enqueue_or_fail(self, generation: Generation, *, locale: str) -> None:
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
                users=self._users,
                quota_refund=self._quota_refund,
                credits=self._credits,
            ).mark_publish_failed(generation)
            raise QueuePublishFailedError(message_for("queue_publish_failed", locale)) from exc

    async def execute(
        self,
        *,
        user: User,
        data: GenerateImageInput,
        locale: str = "pt-BR",
        ip_hash: str | None = None,
    ) -> GenerationOutput:
        clean_prompt = validate_prompt_localized(self._guard, data.prompt, locale)
        if self._topic_guard is not None:
            clean_prompt = await self._topic_guard.validate(clean_prompt)
        check_scope_localized(self._scope_guardrail, clean_prompt, locale)
        clean_negative = (
            validate_prompt_localized(self._guard, data.negative_prompt, locale)
            if data.negative_prompt
            else None
        )

        if self._credits is None and not user.has_quota():
            raise QuotaExceededError("Cota de geracoes esgotada.")

        generation = Generation(
            user_id=user.id,
            kind=GenerationKind.GENERATE,
            prompt=clean_prompt,
            negative_prompt=clean_negative,
            style_preset=data.style_preset,
            aspect_ratio=data.aspect_ratio,
            title=data.title,
            seed=data.seed,
            locale=locale,
            ip_hash=ip_hash,
        )
        if self._credits is not None:
            await self._credits.reset_if_due(user.id)
            await self._credits.consume(
                user.id,
                ref_type="generation",
                ref_id=str(generation.id),
                idempotency_key=f"consume:{generation.id}",
            )
        try:
            if self._prompt_quota is not None:
                await self._prompt_quota.execute(f"user:{user.id}")
        except Exception:
            if self._credits is not None:
                await self._credits.refund(
                    user.id,
                    ref_type="generation",
                    ref_id=str(generation.id),
                    idempotency_key=f"refund:{generation.id}",
                    meta={"reason": "prompt_quota_failed"},
                )
            raise
        if self._credits is None:
            user.consume_credit()
            await self._users.save(user)
        await self._generations.save(generation)
        await self._enqueue_or_fail(generation, locale=locale)
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

        return _to_output(generation)


class GenerateImageAnonymous:
    """Geracao por usuario nao logado (sessao anonima assinada, Bloco 3-A)."""

    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        task_queue: TaskQueuePort,
        prompt_guard: PromptInjectionGuard,
        topic_guard: IPromptTopicGuard | None = None,
        events: EventPublisherPort | None = None,
        prompt_quota: PromptQuotaConsumerPort | None = None,
        quota_refund: PromptQuotaRefundPort | None = None,
        scope_guardrail: ScopeGuardrail | None = None,
    ) -> None:
        self._generations = generations
        self._queue = task_queue
        self._guard = prompt_guard
        self._topic_guard = topic_guard
        self._events = events
        self._prompt_quota = prompt_quota
        self._quota_refund = quota_refund
        self._scope_guardrail = scope_guardrail or ScopeGuardrail()

    async def _enqueue_or_fail(self, generation: Generation, *, locale: str) -> None:
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
                quota_refund=self._quota_refund,
            ).mark_publish_failed(generation)
            raise QueuePublishFailedError(message_for("queue_publish_failed", locale)) from exc

    async def execute(
        self,
        *,
        anonymous_session_id: str,
        data: GenerateImageInput,
        locale: str = "pt-BR",
        ip_hash: str | None = None,
    ) -> GenerationOutput:
        clean_prompt = validate_prompt_localized(self._guard, data.prompt, locale)
        if self._topic_guard is not None:
            clean_prompt = await self._topic_guard.validate(clean_prompt)
        check_scope_localized(self._scope_guardrail, clean_prompt, locale)
        clean_negative = (
            validate_prompt_localized(self._guard, data.negative_prompt, locale)
            if data.negative_prompt
            else None
        )

        if self._prompt_quota is not None:
            await self._prompt_quota.execute(f"anon:{anonymous_session_id}")

        generation = Generation(
            user_id=None,
            anonymous_session_id=anonymous_session_id,
            kind=GenerationKind.GENERATE,
            prompt=clean_prompt,
            negative_prompt=clean_negative,
            style_preset=data.style_preset,
            aspect_ratio=data.aspect_ratio,
            title=data.title,
            seed=data.seed,
            locale=locale,
            ip_hash=ip_hash,
        )
        await self._generations.save(generation)
        await self._enqueue_or_fail(generation, locale=locale)
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

        return _to_output(generation)
