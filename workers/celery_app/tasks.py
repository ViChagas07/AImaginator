"""Tasks Celery do AImaginator.

Padroes:
- autoretry com backoff exponencial (spec secao 14);
- falhas persistentes vao para a DLQ apos max_retries;
- falhas de dominio/motor nao sao reprocessadas (ja foram marcadas FAILED);
- o caso de uso e ASYNC (application layer) — a task sync apenas cria
  o event loop e o wiring (adapter de infra, fronteira do framework).
"""

from __future__ import annotations

import asyncio
from typing import Any

from celery import Task

from modules.observability.correlation import (
    bind_generation_context,
    clear_generation_context,
)
from modules.observability.logging_config import get_logger
from shared_kernel.errors import AImaginatorError, GenerationFinalizationError
from workers.celery_app.celery import celery_app
from workers.celery_app.finalization import ensure_failed_after_retries_sync

logger = get_logger(__name__)

_MAX_RETRIES = 3
_USER_REFUSAL_CODES = {
    "content_blocked_nsfw",
    "content_blocked_gore",
    "content_blocked_hate",
    "content_blocked_self_harm",
    "out_of_scope",
    "prompt_rejected",
    "assistant_unavailable",
}


def _run_async(coro) -> Any:
    return asyncio.run(coro)


async def _is_canceled(redis_client, generation_id: str) -> bool:
    value = await redis_client.get(f"cancel:{generation_id}")
    return value in (b"1", "1")




async def _process_generation_async(generation_id: str, kind: str = "generate") -> None:
    from uuid import UUID

    import httpx
    import redis.asyncio as aioredis

    from infra.database import dispose_engine, session_scope
    from infra.settings import get_settings
    from modules.image_generation.adapters.redis_event_publisher import RedisEventPublisher
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )
    from modules.image_generation.application.use_cases.process_upscale import ProcessUpscale
    from modules.image_generation.contracts import ProcessGeneration
    from modules.image_generation.infra import wiring as gen_wiring
    from modules.prompt_quota.adapters.redis_quota_store import RedisPromptQuotaStore
    from modules.prompt_quota.contracts import RefundPromptQuota
    from modules.users.adapters.credit_ledger_repository import (
        SQLAlchemyCreditLedgerRepository,
    )
    from modules.users.adapters.repository import SQLAlchemyUserRepository
    from modules.users.application.credits import CreditLedgerService
    from workers.celery_app.heartbeat import mark_state

    settings = get_settings()
    mark_state(settings, "busy")
    bind_generation_context(generation_id=generation_id, kind=kind)
    logger.info(
        "generation_processing_started",
        correlation_id=generation_id,
        kind=kind,
    )
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    storage = None
    try:
        guard = gen_wiring.build_prompt_guard(max_length=settings.prompt_max_chars)
        if kind == "upscale":
            storage = gen_wiring.build_object_storage_required(settings)
            async with session_scope() as session:
                await ProcessUpscale(
                    generations=SQLAlchemyGenerationRepository(session),
                    storage=storage,
                    upscaler=gen_wiring.build_upscaler(settings),
                    watermarker=gen_wiring.build_watermarker(settings),
                    metadata_writer=gen_wiring.build_metadata_writer(settings),
                    events=RedisEventPublisher(redis_client),
                    quota_store=RedisPromptQuotaStore(redis_client, namespace="upscale-quota"),
                    c2pa_signer=gen_wiring.build_c2pa_signer(settings),
                    commit=session.commit,
                ).execute(UUID(generation_id), raise_on_failure=False)
            return
        if settings.image_engine in {"sdcpp", "hosted"}:
            storage = gen_wiring.build_object_storage_required(settings)
            assistant = gen_wiring.build_prompt_assistant(settings, http_client=http_client)
            from workers.celery_app.heartbeat import mark_cooling

            agent = gen_wiring.build_engine_image_agent(
                settings=settings,
                guard=guard,
                storage=storage,
                prompt_assistant=assistant,
                cooling_callback=lambda seconds, code: mark_cooling(settings, seconds, code),
                http_client=http_client,
                cancel_check=lambda: _is_canceled(redis_client, generation_id),
            )
        else:
            provider = gen_wiring.build_image_provider(
                settings, redis_client=redis_client, http_client=http_client
            )
            agent = gen_wiring.build_image_agent(provider, guard)
        async with session_scope() as session:
            users = SQLAlchemyUserRepository(session)
            moderation = gen_wiring.build_moderation_service(
                settings=settings,
                session=session,
                users=users,
                redis_client=redis_client,
            )
            use_case = ProcessGeneration(
                generations=SQLAlchemyGenerationRepository(session),
                image_agent=agent,
                events=RedisEventPublisher(redis_client),
                storage=storage,
                users=users,
                moderation=moderation,
                quota_refund=RefundPromptQuota(RedisPromptQuotaStore(redis_client)),
                credits=CreditLedgerService(
                    users=users,
                    ledger=SQLAlchemyCreditLedgerRepository(session),
                    monthly_credits=settings.plan_monthly_credits,
                ),
                commit=session.commit,
                rollback=session.rollback,
                cancel_check=lambda: _is_canceled(redis_client, generation_id),
            )
            await use_case.execute(UUID(generation_id), raise_on_failure=False)
    finally:
        if storage is not None and kind == "edit":
            # Limpeza oportunista: garante a retencao mesmo sem Celery beat.
            try:
                await storage.delete_objects_older_than(
                    "sources/", hours=settings.s3_source_retention_hours
                )
            except Exception:
                logger.warning("purge_sources_failed", exc_info=True)
        await http_client.aclose()
        await redis_client.aclose()
        # Cada task roda em um asyncio.run novo; o pool nao pode atravessar
        # loops fechados (asyncpg: Event loop is closed).
        await dispose_engine()
        mark_state(settings, "idle")
        clear_generation_context()


async def _purge_expired_sources_async() -> int:
    from infra.settings import get_settings
    from modules.image_generation.infra import wiring as gen_wiring

    settings = get_settings()
    if not settings.s3_bucket:
        return 0
    storage = gen_wiring.build_object_storage_required(settings)
    deleted = await storage.delete_objects_older_than(
        "sources/", hours=settings.s3_source_retention_hours
    )
    logger.info("purge_sources_ok", deleted=deleted)
    return deleted


@celery_app.task(
    bind=True,
    name="workers.celery_app.tasks.process_generation_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=_MAX_RETRIES,
)
def process_generation_task(self: Task, generation_id: str, kind: str = "generate") -> None:
    try:
        _run_async(_process_generation_async(generation_id, kind))
    except GenerationFinalizationError as exc:
        logger.error(
            "generation_finalization_failed",
            generation_id=generation_id,
            code=exc.code,
        )
        ensure_failed_after_retries_sync(generation_id, exc.code)
        _send_to_dlq(generation_id, exc.code)
        raise
    except AImaginatorError as exc:
        logger.error(
            "generation_processing_domain_failed",
            generation_id=generation_id,
            code=exc.code,
        )
        ensured = ensure_failed_after_retries_sync(generation_id, exc.code)
        if exc.code not in _USER_REFUSAL_CODES:
            _send_to_dlq(generation_id, exc.code)
        if not ensured:
            raise
    except Exception as exc:
        logger.exception("generation_processing_failed", generation_id=generation_id)
        if self.request.retries >= _MAX_RETRIES:
            ensure_failed_after_retries_sync(generation_id, type(exc).__name__)
            _send_to_dlq(generation_id, type(exc).__name__)
            raise
        raise self.retry(exc=exc, countdown=min(2**self.request.retries * 5, 120)) from exc


def _send_to_dlq(generation_id: str, error: str) -> None:
    """Publica na dead-letter queue para analise/reprocessamento manual."""
    celery_app.send_task(
        "workers.celery_app.tasks.dead_letter_task",
        args=[generation_id, error],
        queue="generation.dlq",
    )


@celery_app.task(name="workers.celery_app.tasks.dead_letter_task")
def dead_letter_task(generation_id: str, error: str) -> None:
    logger.error("generation_dlq", generation_id=generation_id, error_code=error)


@celery_app.task(name="workers.celery_app.tasks.purge_sources_task")
def purge_sources_task() -> int:
    """Remove origens de edicao mais antigas que S3_SOURCE_RETENTION_HOURS."""
    return _run_async(_purge_expired_sources_async())
