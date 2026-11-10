"""Finalizacao de seguranca quando o pipeline nao gravou estado terminal.

Chamado no limite de retries e em falhas de finalizacao. Garante, via CAS:
- estado FAILED persistido antes de qualquer refund;
- refund de credito/cota no maximo uma vez;
- evento terminal publicado antes do DLQ.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from modules.observability.logging_config import get_logger

logger = get_logger(__name__)


def ensure_failed_after_retries_sync(generation_id: str, error_code: str) -> bool:
    """Versao sync para a task Celery (ja fora do event loop da task)."""
    try:
        return asyncio.run(_ensure_failed_after_retries(generation_id, error_code))
    except Exception:
        logger.exception(
            "generation_retry_finalization_failed",
            generation_id=generation_id,
            error_code=error_code,
        )
        return False


async def _ensure_failed_after_retries(generation_id: str, error_code: str) -> bool:
    import redis.asyncio as aioredis

    from infra.database import dispose_engine, session_scope
    from infra.settings import get_settings
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )
    from modules.image_generation.domain.engine_errors import EngineFailedError
    from modules.image_generation.domain.entities import GenerationStatus

    settings = get_settings()
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    terminal = (
        GenerationStatus.DONE,
        GenerationStatus.FAILED,
        GenerationStatus.CANCELED,
    )
    try:
        async with session_scope() as session:
            repo = SQLAlchemyGenerationRepository(session)
            generation = await repo.get_by_id(UUID(generation_id))
            if generation is None:
                return True

            if generation.status in terminal:
                await _refund_once(session, generation, settings, redis_client)
                await _publish_terminal(redis_client, generation)
                return True

            message = EngineFailedError().message
            changed = await repo.transition_if_status(
                generation.id,
                from_statuses=(GenerationStatus.QUEUED, GenerationStatus.PROCESSING),
                to_status=GenerationStatus.FAILED,
                error_message=message,
                error_code="finalize_failed",
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                result_image_url=None,
                result_object_key=None,
                original_object_key=None,
            )
            if not changed:
                current = await repo.get_by_id(generation.id)
                if current is None or current.status not in terminal:
                    return False
                generation = current
                await _refund_once(session, generation, settings, redis_client)
                await _publish_terminal(redis_client, generation)
                return True

            # Persiste FAILED antes de qualquer refund.
            await session.commit()
            generation.status = GenerationStatus.FAILED
            generation.error_message = message
            generation.error_code = "finalize_failed"
            generation.completed_at = datetime.now(UTC)
            generation.updated_at = datetime.now(UTC)
            generation.result_image_url = None
            generation.result_object_key = None
            generation.original_object_key = None
            await _refund_once(session, generation, settings, redis_client)
            await repo.save(generation)
            await session.commit()

        await _publish_terminal(redis_client, generation)
        logger.warning(
            "generation_retry_finalized_failed",
            generation_id=generation_id,
            original_error=error_code,
        )
        return True
    finally:
        await redis_client.aclose()
        await dispose_engine()


async def _refund_once(session, generation, settings, redis_client) -> None:
    from modules.prompt_quota.adapters.redis_quota_store import RedisPromptQuotaStore
    from modules.prompt_quota.contracts import RefundPromptQuota
    from modules.users.adapters.credit_ledger_repository import (
        SQLAlchemyCreditLedgerRepository,
    )
    from modules.users.adapters.repository import SQLAlchemyUserRepository
    from modules.users.application.credits import CreditLedgerService

    if generation.user_id is not None and not generation.credits_refunded:
        try:
            users = SQLAlchemyUserRepository(session)
            credits = CreditLedgerService(
                users=users,
                ledger=SQLAlchemyCreditLedgerRepository(session),
                monthly_credits=settings.plan_monthly_credits,
            )
            await credits.refund(
                generation.user_id,
                amount=generation.credits_cost,
                ref_type="generation",
                ref_id=str(generation.id),
                idempotency_key=f"refund:{generation.id}",
                meta={"reason": "finalize_failed"},
            )
            generation.credits_refunded = True
        except Exception:
            logger.warning(
                "generation_retry_credit_refund_failed",
                generation_id=str(generation.id),
                exc_info=True,
            )

    if not generation.quota_refunded:
        if generation.user_id is not None:
            principal = f"user:{generation.user_id}"
        elif generation.anonymous_session_id:
            principal = f"anon:{generation.anonymous_session_id}"
        else:
            principal = None
        if principal:
            try:
                await RefundPromptQuota(
                    RedisPromptQuotaStore(redis_client)
                ).refund(principal)
                generation.quota_refunded = True
            except Exception:
                logger.warning(
                    "generation_retry_quota_refund_failed",
                    generation_id=str(generation.id),
                    exc_info=True,
                )


async def _publish_terminal(redis_client, generation) -> None:
    from modules.image_generation.adapters.redis_event_publisher import (
        RedisEventPublisher,
    )
    from modules.image_generation.application.schemas import GenerationProgressEvent
    from modules.image_generation.domain.entities import GenerationStatus

    if generation.status not in (GenerationStatus.FAILED, GenerationStatus.CANCELED):
        return
    try:
        await RedisEventPublisher(redis_client).publish_progress(
            GenerationProgressEvent(
                generation_id=generation.id,
                status=generation.status,
                progress=100,
                error=generation.error_message,
                error_code=generation.error_code,
            )
        )
    except Exception:
        logger.warning(
            "generation_retry_terminal_publish_failed",
            generation_id=str(generation.id),
            exc_info=True,
        )
