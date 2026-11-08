"""Reconciliacao de geracoes orfas no startup do worker."""

from __future__ import annotations

import asyncio

from infra.settings import get_settings
from modules.observability.logging_config import get_logger

logger = get_logger(__name__)


def reconcile_stale_generations_sync() -> int:
    """Executa uma passada do reconciliador; nunca impede o worker de subir."""
    try:
        return asyncio.run(_reconcile_stale_generations())
    except Exception:
        logger.warning(
            "queue_reconcile_startup_failed",
            exc_info=True,
        )
        return 0


async def _reconcile_stale_generations() -> int:
    import redis.asyncio as aioredis

    from infra.database import dispose_engine, session_scope
    from modules.image_generation.adapters.redis_event_publisher import (
        RedisEventPublisher,
    )
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )
    from modules.image_generation.application.services.queue_recovery import (
        QueueRecoveryService,
    )
    from modules.prompt_quota.adapters.redis_quota_store import RedisPromptQuotaStore
    from modules.prompt_quota.contracts import RefundPromptQuota
    from modules.users.adapters.repository import SQLAlchemyUserRepository

    settings = get_settings()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        async with session_scope() as session:
            service = QueueRecoveryService(
                generations=SQLAlchemyGenerationRepository(session),
                events=RedisEventPublisher(redis),
                users=SQLAlchemyUserRepository(session),
                quota_refund=RefundPromptQuota(RedisPromptQuotaStore(redis)),
                stale_seconds=settings.queue_stale_seconds,
            )
            reconciled = await service.reconcile_all()
    finally:
        await redis.aclose()
        # O worker usa asyncio.run por task; nao deixe o pool preso ao loop
        # de startup (asyncpg e loop-bound).
        await dispose_engine()
    if reconciled:
        logger.warning("queue_reconcile_startup", reconciled=reconciled)
    return reconciled
