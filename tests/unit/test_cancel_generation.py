"""Cancelamento: fila, processamento, refunds e ownership."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.image_generation.application.use_cases.cancel_generation import (
    CancelGeneration,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from shared_kernel.errors import ForbiddenError


class _Repo:
    def __init__(self, generation) -> None:
        self.generation = generation
        self.saved = False

    async def get_by_id(self, generation_id):
        return self.generation

    async def save(self, generation):
        self.saved = True
        self.generation = generation


class _Events:
    def __init__(self) -> None:
        self.events = []

    async def publish_progress(self, event):
        self.events.append(event)


class _Redis:
    def __init__(self) -> None:
        self.keys = {}

    async def setex(self, key, ttl, value):
        self.keys[key] = (ttl, value)


class _Credits:
    def __init__(self) -> None:
        self.refunds = []

    async def refund(self, user_id, **kwargs):
        self.refunds.append((user_id, kwargs))


class _Quota:
    def __init__(self) -> None:
        self.refunds = []

    async def refund(self, principal):
        self.refunds.append(principal)
        return True


def _generation(status=GenerationStatus.QUEUED, user_id=None):
    generation = Generation(
        user_id=user_id or uuid4(),
        kind=GenerationKind.GENERATE,
        prompt="x",
    )
    if status is GenerationStatus.PROCESSING:
        generation.transition_to(GenerationStatus.PROCESSING)
    return generation


@pytest.mark.unit
async def test_cancelar_na_fila_transiciona_e_refunda() -> None:
    generation = _generation()
    repo, events, redis, credits, quota = (
        _Repo(generation),
        _Events(),
        _Redis(),
        _Credits(),
        _Quota(),
    )
    result = await CancelGeneration(
        generations=repo,
        events=events,
        redis=redis,
        credits=credits,
        quota_refund=quota,
    ).execute(user_id=generation.user_id, generation_id=generation.id)

    assert result["status"] == "canceled"
    assert generation.status is GenerationStatus.CANCELED
    assert generation.credits_refunded is True
    assert generation.quota_refunded is True
    assert credits.refunds and quota.refunds == [f"user:{generation.user_id}"]
    assert events.events[-1].status is GenerationStatus.CANCELED
    assert redis.keys


@pytest.mark.unit
async def test_cancelar_processando_apenas_sinaliza() -> None:
    generation = _generation(GenerationStatus.PROCESSING)
    redis = _Redis()
    result = await CancelGeneration(
        generations=_Repo(generation), events=_Events(), redis=redis
    ).execute(user_id=generation.user_id, generation_id=generation.id)

    assert result["status"] == "cancel_requested"
    assert generation.status is GenerationStatus.PROCESSING
    assert redis.keys


@pytest.mark.unit
async def test_nao_pode_cancelar_geracao_de_outro() -> None:
    generation = _generation()
    with pytest.raises(ForbiddenError):
        await CancelGeneration(
            generations=_Repo(generation), events=_Events(), redis=_Redis()
        ).execute(user_id=uuid4(), generation_id=generation.id)
