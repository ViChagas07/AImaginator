"""Wiring de dependencias do modulo image_generation (camada infra do modulo).

Monta o grafo de objetos do modulo a partir das implementacoes
concretas, mantendo apps/api livre de detalhes de construcao.
"""

from __future__ import annotations

from typing import Any

import httpx

from infra.settings import Settings
from modules.image_generation.adapters.ai_agents.llm_client import (
    OpenAICompatibleLlmClient,
)
from modules.image_generation.adapters.ai_agents.orchestrator import LangGraphImageAgent
from modules.image_generation.adapters.ai_agents.prompt_classifier import (
    GeminiPromptClassifier,
    HttpPromptClassifier,
    StubPromptClassifier,
)
from modules.image_generation.adapters.ai_agents.providers import (
    HttpImageProvider,
    ImageProvider,
    StubImageEditor,
    StubImageGenerator,
    StubImageProvider,
)
from modules.image_generation.adapters.image_moderation import (
    FakeImageModerator,
    LocalImageModerator,
)
from modules.image_generation.adapters.image_processing import (
    AiMetadataWriter,
    C2PASigner,
    PillowWatermarker,
)
from modules.image_generation.adapters.lms_cli import LmsCliUnloader
from modules.image_generation.adapters.redis_penalty_store import RedisPenaltyStore
from modules.image_generation.adapters.repositories.moderation_repository import (
    SQLAlchemyModerationEventRepository,
)
from modules.image_generation.adapters.s3_storage import S3ObjectStorage
from modules.image_generation.adapters.sdcpp import (
    SdCppImageEditor,
    SdCppImageGenerator,
)
from modules.image_generation.adapters.secure_image_fetcher import SecureImageFetcher
from modules.image_generation.adapters.upscale import EsrganUpscaler, LanczosUpscaler
from modules.image_generation.application.ports import (
    ImageEditorPort,
    ImageFetcherPort,
    ImageGeneratorPort,
    ImageModerationThresholds,
    ImageModeratorPort,
    ImageWatermarkerPort,
    ObjectStoragePort,
    PromptAssistantPort,
    UpscalerPort,
)
from modules.image_generation.application.services.moderation import ModerationService
from modules.image_generation.application.services.prompt_assistant import (
    PromptAssistant,
)
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.prompt_topic_guard import (
    IPromptClassifier,
    PromptTopicGuard,
)
from modules.image_generation.domain.url_policy import UrlPolicy
from modules.rate_limiting.bulkhead import bulkhead_registry
from modules.rate_limiting.circuit_breaker import CircuitBreaker


def build_prompt_guard(*, max_length: int = 2000) -> PromptInjectionGuard:
    return PromptInjectionGuard(max_length=max_length)


def build_prompt_assistant(
    settings: Settings, *, http_client: httpx.AsyncClient
) -> PromptAssistantPort:
    llm = OpenAICompatibleLlmClient(
        http_client=http_client,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
        ttl_seconds=settings.llm_ttl_seconds,
        reasoning_effort=settings.llm_reasoning_effort,
        max_output_tokens_retry=settings.llm_max_output_tokens_retry,
        debug_log_content=settings.llm_debug_log_content_enabled,
    )
    return PromptAssistant(
        llm=llm,
        block_confidence=settings.llm_block_confidence,
        debug_log_content=settings.llm_debug_log_content_enabled,
    )


def build_llm_unloader(settings: Settings) -> LmsCliUnloader | None:
    if not settings.llm_unload_after_use:
        return None
    return LmsCliUnloader(
        cli_path=settings.lms_cli_path,
        timeout_seconds=settings.llm_unload_timeout_seconds,
    )


def build_moderation_service(
    *,
    settings: Settings,
    session,
    users,
    redis_client,
) -> ModerationService:
    return ModerationService(
        events=SQLAlchemyModerationEventRepository(session),
        users=users,
        penalty_store=RedisPenaltyStore(redis_client),
        warn_at=settings.mod_warn_at,
        block_at=settings.mod_block_at,
        review_at=settings.mod_review_at,
        block_minutes=settings.mod_block_minutes,
        review_block_hours=settings.mod_review_block_hours,
        window_hours=settings.moderation_window_hours,
        store_prompt_text=settings.moderation_store_prompt_text,
    )


def build_topic_classifier(
    settings: Settings, *, http_client: httpx.AsyncClient
) -> IPromptClassifier:
    provider = settings.topic_classifier_provider
    if provider == "stub" or not settings.topic_classifier_api_key:
        return StubPromptClassifier()
    if provider == "gemini":
        return GeminiPromptClassifier(
            http_client=http_client,
            api_key=settings.topic_classifier_api_key,
            model=settings.topic_classifier_model,
        )
    # Default: OpenAI-compatible Chat Completions
    return HttpPromptClassifier(
        http_client=http_client,
        api_base_url=settings.topic_classifier_api_base_url,
        api_key=settings.topic_classifier_api_key,
        model=settings.topic_classifier_model,
    )


def build_topic_guard(settings: Settings, *, http_client: httpx.AsyncClient) -> PromptTopicGuard:
    return PromptTopicGuard(
        classifier=build_topic_classifier(settings, http_client=http_client),
        timeout_seconds=settings.topic_classifier_timeout_seconds,
    )


def build_url_policy(settings: Settings) -> UrlPolicy:
    return UrlPolicy(settings.allowed_image_domains)


def build_object_storage(settings: Settings) -> S3ObjectStorage | None:
    """Storage S3/MinIO quando configurado; None mantem o modo stub legado."""
    if not settings.s3_bucket:
        return None
    return S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        public_endpoint_url=settings.s3_public_endpoint_url,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key or settings.aws_access_key_id,
        secret_key=settings.s3_secret_key or settings.aws_secret_access_key,
        region=settings.s3_region,
        presign_expires_seconds=settings.s3_presign_expires_seconds,
        auto_create_bucket=not settings.is_production,
    )


def build_object_storage_required(settings: Settings) -> ObjectStoragePort:
    storage = build_object_storage(settings)
    if storage is None:
        msg = "Storage S3 nao configurado (S3_BUCKET ausente)."
        raise RuntimeError(msg)
    return storage


def build_image_moderator(settings: Settings) -> ImageModeratorPort | None:
    if not settings.image_moderation_enabled:
        return None
    if settings.image_moderator == "fake":
        return FakeImageModerator()
    return LocalImageModerator(
        nsfw_model_path=settings.image_nsfw_model_path,
        clip_model_path=settings.image_clip_model_path,
        thresholds=ImageModerationThresholds(
            sexual=settings.image_nsfw_threshold,
            gore=settings.image_gore_threshold,
            hate=settings.image_hate_threshold,
            self_harm=settings.image_self_harm_threshold,
        ),
    )


def build_watermarker(settings: Settings) -> ImageWatermarkerPort:
    return PillowWatermarker(
        logo_path=settings.watermark_logo_path,
        width_ratio=settings.watermark_width_ratio,
        min_width_px=settings.watermark_min_width_px,
        margin_ratio=settings.watermark_margin_ratio,
        opacity=settings.watermark_opacity,
        shadow=settings.watermark_shadow,
    )


def build_metadata_writer(settings: Settings) -> AiMetadataWriter:
    return AiMetadataWriter()


def build_c2pa_signer(settings: Settings) -> C2PASigner:
    return C2PASigner(
        enabled=settings.c2pa_enabled,
        cert_path=settings.c2pa_cert_path,
        key_path=settings.c2pa_key_path,
    )


def build_upscaler(settings: Settings) -> UpscalerPort:
    if settings.upscale_engine == "esrgan":
        return EsrganUpscaler(settings)
    return LanczosUpscaler()


def build_secure_image_fetcher(
    settings: Settings, *, http_client: httpx.AsyncClient
) -> ImageFetcherPort:
    return SecureImageFetcher(
        url_policy=build_url_policy(settings),
        http_client=http_client,
        max_bytes=settings.edit_upload_max_bytes,
    )


def build_image_generator(settings: Settings) -> ImageGeneratorPort:
    if settings.image_engine == "sdcpp":
        return SdCppImageGenerator(settings)
    return StubImageGenerator()


def build_image_editor(settings: Settings) -> ImageEditorPort:
    if settings.image_engine == "sdcpp":
        return SdCppImageEditor(settings)
    return StubImageEditor()


def build_image_provider(
    settings: Settings, *, redis_client: Any, http_client: httpx.AsyncClient
) -> ImageProvider:
    if settings.ai_image_provider == "stub":
        return StubImageProvider(
            storage_base_url=settings.storage_bucket_url or "https://picsum.photos"
        )
    circuit = CircuitBreaker(
        redis_client,
        name="ai_image_provider",
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_seconds=settings.circuit_breaker_recovery_seconds,
    )
    bulkhead = bulkhead_registry.get_or_create("ai_image_provider", max_concurrent=8, max_queued=50)
    return HttpImageProvider(
        http_client=http_client,
        circuit_breaker=circuit,
        bulkhead=bulkhead,
        api_base_url=settings.ai_image_api_base_url,
        api_key=settings.ai_image_api_key,
    )


def build_image_agent(provider: ImageProvider, guard: PromptInjectionGuard) -> LangGraphImageAgent:
    return LangGraphImageAgent(provider=provider, prompt_guard=guard)


def build_engine_image_agent(
    *,
    settings: Settings,
    guard: PromptInjectionGuard,
    storage: ObjectStoragePort | None,
    prompt_assistant: PromptAssistantPort | None = None,
) -> LangGraphImageAgent:
    return LangGraphImageAgent(
        prompt_guard=guard,
        generator=build_image_generator(settings),
        editor=build_image_editor(settings),
        storage=storage,
        prompt_assistant=prompt_assistant,
        llm_unloader=build_llm_unloader(settings),
        block_confidence=settings.llm_block_confidence,
        image_moderator=build_image_moderator(settings),
        image_moderation_enabled=settings.image_moderation_enabled,
        watermarker=build_watermarker(settings),
        metadata_writer=build_metadata_writer(settings),
        c2pa_signer=build_c2pa_signer(settings),
    )
