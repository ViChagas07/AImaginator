"""Tasks Celery do AImaginator.

Padroes:
- autoretry com backoff exponencial (spec secao 14);
- falhas persistentes vao para a DLQ apos max_retries;
- o caso de uso e ASYNC (application layer) — a task sync apenas cria
  o event loop e o wiring (adapter de infra, fronteira do framework).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import Task

from workers.celery_app.celery import celery_app

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


def _run_async(coro) -> Any:
    return asyncio.run(coro)


async def _process_generation_async(generation_id: str) -> None:
    from uuid import UUID

    import redis.asyncio as aioredis

    from infra.database import session_scope
    from infra.settings import get_settings
    from modules.image_generation.adapters.redis_event_publisher import RedisEventPublisher
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )
    from modules.image_generation.contracts import ProcessGeneration
    from modules.image_generation.infra import wiring as gen_wiring
    import httpx

    settings = get_settings()
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    try:
        guard = gen_wiring.build_prompt_guard()
        provider = gen_wiring.build_image_provider(
            settings, redis_client=redis_client, http_client=http_client
        )
        agent = gen_wiring.build_image_agent(provider, guard)
        async with session_scope() as session:
            use_case = ProcessGeneration(
                generations=SQLAlchemyGenerationRepository(session),
                image_agent=agent,
                events=RedisEventPublisher(redis_client),
            )
            await use_case.execute(UUID(generation_id))
    finally:
        await http_client.aclose()
        await redis_client.aclose()


@celery_app.task(
    bind=True,
    name="workers.celery_app.tasks.process_generation_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=_MAX_RETRIES,
)
def process_generation_task(self: Task, generation_id: str) -> None:
    try:
        _run_async(_process_generation_async(generation_id))
    except Exception as exc:
        logger.exception("Falha ao processar geracao %s", generation_id)
        if self.request.retries >= _MAX_RETRIES:
            _send_to_dlq(generation_id, str(exc))
            return
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
    logger.error("DLQ: geracao %s falhou definitivamente: %s", generation_id, error)
