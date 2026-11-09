"""Caso de uso: editar imagem existente (URL validada anti-SSRF)."""

from __future__ import annotations

from modules.image_generation.application.guardrails import (
    check_scope_localized,
    validate_prompt_localized,
)
from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports import (
    EventPublisherPort,
    GenerationRepositoryPort,
    ImageFetcherPort,
    ObjectStoragePort,
    TaskQueuePort,
)
from modules.image_generation.application.schemas import (
    EditImageInput,
    GenerateImageInput,
    GenerationOutput,
    GenerationProgressEvent,
)
from modules.image_generation.application.services.queue_recovery import (
    QueueRecoveryService,
)
from modules.image_generation.application.use_cases.generate_image import _to_output
from modules.image_generation.domain.entities import Generation, GenerationKind, GenerationStatus
from modules.image_generation.domain.image_bytes import inspect_image_bytes
from modules.image_generation.domain.image_upload import (
    inspect_uploaded_image,
    normalize_uploaded_image,
)
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.prompt_topic_guard import IPromptTopicGuard
from modules.image_generation.domain.scope_guard import ScopeGuardrail
from modules.image_generation.domain.storage_errors import StorageUnavailableError
from modules.image_generation.domain.url_policy import UrlPolicy
from modules.observability.logging_config import get_logger
from modules.prompt_quota.contracts import (
    PromptQuotaConsumerPort,
    PromptQuotaRefundPort,
)
from modules.users.application.credits import CreditLedgerService
from modules.users.contracts import User, UserRepositoryPort
from shared_kernel.errors import DomainError, ForbiddenError, NotFoundError, QuotaExceededError
from shared_kernel.security_errors import (
    OriginalUnavailableError,
    QueuePublishFailedError,
)

logger = get_logger(__name__)


async def _enqueue_or_fail(
    *,
    queue: TaskQueuePort,
    generation: Generation,
    generations: GenerationRepositoryPort,
    events: EventPublisherPort | None,
    users: UserRepositoryPort | None,
    quota_refund: PromptQuotaRefundPort | None,
    credits: CreditLedgerService | None,
    locale: str,
) -> None:
    try:
        queue.enqueue_generation(generation.id, kind=generation.kind.value)
    except Exception as exc:
        logger.warning(
            "queue_publish_failed",
            correlation_id=str(generation.id),
            error_type=type(exc).__name__,
        )
        await QueueRecoveryService(
            generations=generations,
            events=events,
            users=users,
            quota_refund=quota_refund,
            credits=credits,
        ).mark_publish_failed(generation)
        raise QueuePublishFailedError(message_for("queue_publish_failed", locale)) from exc


class EditImageFromPrompt:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        users: UserRepositoryPort,
        task_queue: TaskQueuePort,
        prompt_guard: PromptInjectionGuard,
        url_policy: UrlPolicy,
        topic_guard: IPromptTopicGuard | None = None,
        events: EventPublisherPort | None = None,
        prompt_quota: PromptQuotaConsumerPort | None = None,
        quota_refund: PromptQuotaRefundPort | None = None,
        credits: CreditLedgerService | None = None,
        image_fetcher: ImageFetcherPort | None = None,
        storage: ObjectStoragePort | None = None,
        max_upload_bytes: int = 10 * 1024 * 1024,
        max_upload_dimension: int = 8192,
        max_upload_pixels: int = 40_000_000,
        scope_guardrail: ScopeGuardrail | None = None,
    ) -> None:
        self._generations = generations
        self._users = users
        self._queue = task_queue
        self._guard = prompt_guard
        self._topic_guard = topic_guard
        self._url_policy = url_policy
        self._events = events
        self._prompt_quota = prompt_quota
        self._quota_refund = quota_refund
        self._credits = credits
        self._image_fetcher = image_fetcher
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes
        self._max_upload_dimension = max_upload_dimension
        self._max_upload_pixels = max_upload_pixels
        self._scope_guardrail = scope_guardrail or ScopeGuardrail()

    async def execute(
        self,
        *,
        user: User,
        data: EditImageInput,
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

        parent = None
        source_url: str | None = None
        source_image: bytes | None = None
        if data.source_generation_id is not None:
            parent = await self._generations.get_by_id(data.source_generation_id)
            if parent is None:
                raise NotFoundError("Geracao de origem nao encontrada.")
            if parent.user_id != user.id:
                raise ForbiddenError("Acesso negado a esta geracao.")
            if parent.status is not GenerationStatus.DONE:
                raise DomainError("A geracao de origem ainda nao esta pronta.")
            if not parent.original_object_key:
                raise OriginalUnavailableError(message_for("original_unavailable", locale))
        else:
            if data.source_image_url is None:
                raise DomainError("Imagem de origem obrigatoria.")
            source_url = self._url_policy.validate(str(data.source_image_url))
            source_image = await self._download_source(source_url)

        if self._credits is None and not user.has_quota():
            raise QuotaExceededError("Cota de geracoes esgotada.")

        generation = Generation(
            user_id=user.id,
            kind=GenerationKind.EDIT,
            prompt=clean_prompt,
            negative_prompt=clean_negative,
            style_preset=data.style_preset,
            aspect_ratio=data.aspect_ratio,
            source_image_url=source_url,
            source_object_key=parent.original_object_key if parent else None,
            parent_generation_id=parent.id if parent else None,
            seed=data.seed,
            locale=locale,
            ip_hash=ip_hash,
        )
        if source_image is not None:
            await self._store_source(generation, source_image)

        try:
            if self._prompt_quota is not None:
                await self._prompt_quota.execute(f"user:{user.id}")
        except Exception:
            if generation.source_object_key and self._storage is not None:
                try:
                    await self._storage.delete_object(generation.source_object_key)
                except Exception:  # noqa: S110 - nao mascarar o erro original
                    pass
            raise

        if self._credits is not None:
            await self._credits.reset_if_due(user.id)
            await self._credits.consume(
                user.id,
                ref_type="generation",
                ref_id=str(generation.id),
                idempotency_key=f"consume:{generation.id}",
            )
        else:
            user.consume_credit()
            await self._users.save(user)
        await self._generations.save(generation)
        await _enqueue_or_fail(
            queue=self._queue,
            generation=generation,
            generations=self._generations,
            events=self._events,
            users=self._users,
            quota_refund=self._quota_refund,
            credits=self._credits,
            locale=locale,
        )
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

    async def _download_source(self, source_url: str) -> bytes | None:
        if self._image_fetcher is None or self._storage is None:
            return None
        data = await self._image_fetcher.fetch(source_url)
        metadata = inspect_image_bytes(data, strict=False)
        if len(data) > self._max_upload_bytes:
            raise DomainError("Imagem de origem excede o tamanho maximo permitido.")
        if (
            metadata.width > self._max_upload_dimension
            or metadata.height > self._max_upload_dimension
            or metadata.width * metadata.height > self._max_upload_pixels
        ):
            raise DomainError("Imagem de origem excede o limite de dimensoes/pixels.")
        return normalize_uploaded_image(data, max_pixels=self._max_upload_pixels)

    async def _store_source(self, generation: Generation, data: bytes) -> None:
        if self._storage is None:
            return
        key = f"sources/{generation.id}/source.png"
        try:
            await self._storage.put_object(key, data, content_type="image/png")
        except Exception as exc:
            raise StorageUnavailableError() from exc
        generation.source_object_key = key


class CreateEditFromUpload:
    """Cria e enfileira uma edicao a partir de uma imagem enviada por upload."""

    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        users: UserRepositoryPort,
        task_queue: TaskQueuePort,
        prompt_guard: PromptInjectionGuard,
        storage: ObjectStoragePort,
        topic_guard: IPromptTopicGuard | None = None,
        events: EventPublisherPort | None = None,
        prompt_quota: PromptQuotaConsumerPort | None = None,
        quota_refund: PromptQuotaRefundPort | None = None,
        credits: CreditLedgerService | None = None,
        max_upload_bytes: int = 10 * 1024 * 1024,
        max_upload_dimension: int = 8192,
        max_upload_pixels: int = 40_000_000,
        scope_guardrail: ScopeGuardrail | None = None,
    ) -> None:
        self._generations = generations
        self._users = users
        self._queue = task_queue
        self._guard = prompt_guard
        self._topic_guard = topic_guard
        self._storage = storage
        self._events = events
        self._prompt_quota = prompt_quota
        self._quota_refund = quota_refund
        self._credits = credits
        self._max_upload_bytes = max_upload_bytes
        self._max_upload_dimension = max_upload_dimension
        self._max_upload_pixels = max_upload_pixels
        self._scope_guardrail = scope_guardrail or ScopeGuardrail()

    async def execute(
        self,
        *,
        user: User,
        data: GenerateImageInput,
        image_bytes: bytes,
        declared_content_type: str | None,
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
        inspect_uploaded_image(
            image_bytes,
            declared_content_type=declared_content_type,
            max_bytes=self._max_upload_bytes,
            max_dimension=self._max_upload_dimension,
            max_pixels=self._max_upload_pixels,
        )
        normalized = normalize_uploaded_image(image_bytes, max_pixels=self._max_upload_pixels)

        if self._credits is None and not user.has_quota():
            raise QuotaExceededError("Cota de geracoes esgotada.")

        generation = Generation(
            user_id=user.id,
            kind=GenerationKind.EDIT,
            prompt=clean_prompt,
            negative_prompt=clean_negative,
            style_preset=data.style_preset,
            aspect_ratio=data.aspect_ratio,
            seed=data.seed,
            locale=locale,
            ip_hash=ip_hash,
        )
        key = f"sources/{generation.id}/source.png"
        try:
            await self._storage.put_object(key, normalized, content_type="image/png")
        except Exception as exc:
            raise StorageUnavailableError() from exc
        generation.source_object_key = key

        try:
            if self._prompt_quota is not None:
                await self._prompt_quota.execute(f"user:{user.id}")
        except Exception:
            try:
                await self._storage.delete_object(key)
            except Exception:  # noqa: S110 - nao mascarar o erro original
                pass
            raise

        if self._credits is not None:
            await self._credits.reset_if_due(user.id)
            await self._credits.consume(
                user.id,
                ref_type="generation",
                ref_id=str(generation.id),
                idempotency_key=f"consume:{generation.id}",
            )
        else:
            user.consume_credit()
            await self._users.save(user)
        await self._generations.save(generation)
        await _enqueue_or_fail(
            queue=self._queue,
            generation=generation,
            generations=self._generations,
            events=self._events,
            users=self._users,
            quota_refund=self._quota_refund,
            credits=self._credits,
            locale=locale,
        )
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
