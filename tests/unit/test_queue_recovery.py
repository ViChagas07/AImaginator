"""Reconciliacao de geracoes orfas e falha de publish (relogio falso)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from prometheus_client import REGISTRY

from modules.image_generation.application.services.queue_recovery import (
    QueueRecoveryService,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from tests.conftest import (
    InMemoryGenerationRepository,
    InMemoryUserRepository,
    SpyEventPublisher,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class _Refund:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def refund(self, principal_id: str) -> bool:
        self.calls.append(principal_id)
        return True


def _generation(
    *,
    status: GenerationStatus = GenerationStatus.QUEUED,
    age_seconds: int = 901,
    user_id=None,
    anonymous_session_id: str | None = None,
    locale: str = "en",
) -> Generation:
    generation = Generation(
        user_id=user_id,
        anonymous_session_id=anonymous_session_id,
        kind=GenerationKind.GENERATE,
        prompt="um castelo",
        locale=locale,
    )
    if status is GenerationStatus.PROCESSING:
        generation.transition_to(GenerationStatus.PROCESSING)
    generation.updated_at = NOW - timedelta(seconds=age_seconds)
    generation.created_at = generation.updated_at
    return generation


def _service(
    generations,
    *,
    users=None,
    refund=None,
    events=None,
    stale_seconds: int = 900,
):
    return QueueRecoveryService(
        generations=generations,
        events=events or SpyEventPublisher(),
        users=users,
        quota_refund=refund,
        stale_seconds=stale_seconds,
        clock=lambda: NOW,
    )


@pytest.mark.unit
async def test_generation_obsoleta_vira_queue_lost_com_refunds_idempotentes(
    sample_user,
) -> None:
    repo = InMemoryGenerationRepository()
    sample_user.generation_credits = 4
    users = InMemoryUserRepository(sample_user)
    refund = _Refund()
    events = SpyEventPublisher()
    generation = _generation(user_id=sample_user.id)
    await repo.save(generation)

    service = _service(repo, users=users, refund=refund, events=events)
    assert await service.reconcile_generation(generation.id) is True

    saved = await repo.get_by_id(generation.id)
    assert saved is not None
    assert saved.status == GenerationStatus.FAILED
    assert saved.error_code == "queue_lost"
    assert saved.error_message
    assert saved.credits_refunded is True
    assert saved.quota_refunded is True
    assert saved.updated_at == NOW
    assert sample_user.generation_credits == 5
    assert refund.calls == [f"user:{sample_user.id}"]
    assert events.events[-1].status == GenerationStatus.FAILED
    assert events.events[-1].error_code == "queue_lost"

    assert await service.reconcile_generation(generation.id) is False
    assert sample_user.generation_credits == 5
    assert refund.calls == [f"user:{sample_user.id}"]


@pytest.mark.unit
async def test_processing_antigo_tambem_e_reconciliado() -> None:
    repo = InMemoryGenerationRepository()
    generation = _generation(status=GenerationStatus.PROCESSING, anonymous_session_id="anon-1")
    await repo.save(generation)

    assert await _service(repo).reconcile_generation(generation.id) is True
    saved = await repo.get_by_id(generation.id)
    assert saved is not None and saved.status == GenerationStatus.FAILED


@pytest.mark.unit
async def test_nao_reconcilia_fresca_nem_terminal() -> None:
    repo = InMemoryGenerationRepository()
    fresh = _generation(age_seconds=100)
    done = _generation(age_seconds=5000)
    done.transition_to(GenerationStatus.PROCESSING)
    done.attach_result("https://cdn.example/x.png")
    await repo.save(fresh)
    await repo.save(done)

    service = _service(repo)
    assert await service.reconcile_generation(fresh.id) is False
    assert await service.reconcile_generation(done.id) is False
    assert (await repo.get_by_id(fresh.id)).status == GenerationStatus.QUEUED
    assert (await repo.get_by_id(done.id)).status == GenerationStatus.DONE


@pytest.mark.unit
async def test_reconcile_all_e_por_usuario(sample_user) -> None:
    repo = InMemoryGenerationRepository()
    mine = _generation(user_id=sample_user.id)
    other = _generation(user_id=uuid4())
    fresh = _generation(user_id=sample_user.id, age_seconds=10)
    for generation in (mine, other, fresh):
        await repo.save(generation)

    assert await _service(repo).reconcile_user(sample_user.id) == 1
    assert (await repo.get_by_id(mine.id)).status == GenerationStatus.FAILED
    assert (await repo.get_by_id(other.id)).status == GenerationStatus.QUEUED
    assert (await repo.get_by_id(fresh.id)).status == GenerationStatus.QUEUED

    assert await _service(repo).reconcile_all() == 1
    assert (await repo.get_by_id(other.id)).status == GenerationStatus.FAILED


@pytest.mark.unit
async def test_publish_failure_nao_impede_persistencia() -> None:
    class _BrokenEvents:
        async def publish_progress(self, event) -> None:
            raise RuntimeError("redis fora")

    repo = InMemoryGenerationRepository()
    generation = _generation()
    await repo.save(generation)

    service = _service(repo, events=_BrokenEvents())
    assert await service.reconcile_generation(generation.id) is True
    saved = await repo.get_by_id(generation.id)
    assert saved is not None and saved.status == GenerationStatus.FAILED


@pytest.mark.unit
async def test_mark_publish_failed_usa_codigo_estavel() -> None:
    repo = InMemoryGenerationRepository()
    generation = _generation(age_seconds=0)
    await repo.save(generation)

    before = (
        REGISTRY.get_sample_value(
            "aimaginator_queue_reconciled_total",
            {"code": "queue_publish_failed"},
        )
        or 0
    )
    assert await _service(repo).mark_publish_failed(generation) is True
    saved = await repo.get_by_id(generation.id)
    assert saved is not None
    assert saved.status == GenerationStatus.FAILED
    assert saved.error_code == "queue_publish_failed"
    after = (
        REGISTRY.get_sample_value(
            "aimaginator_queue_reconciled_total",
            {"code": "queue_publish_failed"},
        )
        or 0
    )
    assert after == before + 1
