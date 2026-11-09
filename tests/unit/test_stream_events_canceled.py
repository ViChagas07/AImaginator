"""SSE: cancelado e terminal, sem KeyError e sem evento duplicado."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import fakeredis.aioredis
import pytest

from modules.image_generation.application.stream_events import (
    event_for_generation,
    sse_event,
    stream_generation_events,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from tests.conftest import InMemoryGenerationRepository


def _canceled_generation() -> Generation:
    generation = Generation(
        user_id=uuid4(),
        kind=GenerationKind.GENERATE,
        prompt="cabana",
    )
    generation.transition_to(
        GenerationStatus.CANCELED,
        error="Geracao cancelada.",
        error_code="canceled",
    )
    return generation


@pytest.mark.unit
def test_evento_cancelado_tem_stage_e_progresso_final() -> None:
    event = event_for_generation(_canceled_generation())
    assert event.status is GenerationStatus.CANCELED
    assert event.progress == 100
    assert event.stage == "canceled"
    assert event.error == "Geracao cancelada."
    assert event.error_code == "canceled"

    sse = sse_event(event)
    assert sse["event"] == "canceled"
    assert json.loads(sse["data"])["status"] == "canceled"


@pytest.mark.unit
async def test_stream_de_cancelado_emite_evento_terminal_e_encerra() -> None:
    repo = InMemoryGenerationRepository()
    generation = _canceled_generation()
    await repo.save(generation)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    stream = stream_generation_events(
        generation_id=generation.id,
        generations=repo,
        redis=redis,
        max_seconds=10,
    )
    event = await asyncio.wait_for(anext(stream), timeout=2)
    assert event["event"] == "canceled"

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=2)

    await stream.aclose()
    await redis.aclose()
