"""Testes do SSE resiliente: estado inicial + Pub/Sub (Fase 2, Bloco 6)."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import fakeredis.aioredis
import pytest
from prometheus_client import REGISTRY

from modules.image_generation.application.ports import stream_channel
from modules.image_generation.application.schemas import GenerationProgressEvent
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


def _generation(status: GenerationStatus = GenerationStatus.QUEUED) -> Generation:
    generation = Generation(
        user_id=uuid4(),
        kind=GenerationKind.GENERATE,
        prompt="um castelo",
    )
    if status == GenerationStatus.PROCESSING:
        generation.transition_to(GenerationStatus.PROCESSING)
    elif status == GenerationStatus.DONE:
        generation.transition_to(GenerationStatus.PROCESSING)
        generation.attach_result("https://cdn.example/result.png")
    elif status == GenerationStatus.FAILED:
        generation.warning_level = 1
        generation.warning_message = "aviso localizado"
        generation.transition_to(
            GenerationStatus.FAILED, error="falha", error_code="engine_timeout"
        )
    return generation


@pytest.mark.unit
def test_evento_de_done_carrega_result_image_url() -> None:
    event = event_for_generation(_generation(GenerationStatus.DONE))
    assert event.status == GenerationStatus.DONE
    assert event.progress == 100
    assert event.result_image_url == "https://cdn.example/result.png"


@pytest.mark.unit
def test_evento_de_failed_carrega_error() -> None:
    event = event_for_generation(_generation(GenerationStatus.FAILED))
    assert event.status == GenerationStatus.FAILED
    assert event.error == "falha"
    assert event.error_code == "engine_timeout"
    assert event.warning_level == 1
    assert event.warning_message == "aviso localizado"


@pytest.mark.unit
def test_payload_sse_usa_os_nomes_reais_do_backend() -> None:
    event = sse_event(event_for_generation(_generation(GenerationStatus.DONE)))
    payload = json.loads(event["data"])
    assert event["event"] == "result"
    assert payload["progress"] == 100
    assert payload["result_image_url"] == "https://cdn.example/result.png"
    assert "percent" not in payload
    assert "imageUrl" not in payload


@pytest.mark.unit
async def test_conexao_depois_do_termino_emite_result_imediatamente() -> None:
    repo = InMemoryGenerationRepository()
    generation = _generation(GenerationStatus.DONE)
    await repo.save(generation)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    stream = stream_generation_events(
        generation_id=generation.id,
        generations=repo,
        redis=redis,
        max_seconds=10,
    )
    event = await asyncio.wait_for(anext(stream), timeout=2)
    assert event["event"] == "result"
    payload = json.loads(event["data"])
    assert payload["result_image_url"] == "https://cdn.example/result.png"
    await stream.aclose()
    await redis.aclose()


@pytest.mark.unit
async def test_conexao_durante_processamento_emite_progress_e_result() -> None:
    repo = InMemoryGenerationRepository()
    generation = _generation(GenerationStatus.PROCESSING)
    await repo.save(generation)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    stream = stream_generation_events(
        generation_id=generation.id,
        generations=repo,
        redis=redis,
        max_seconds=10,
    )
    first = await asyncio.wait_for(anext(stream), timeout=2)
    assert first["event"] == "progress"
    assert json.loads(first["data"])["status"] == "processing"

    await redis.publish(
        stream_channel(generation.id),
        GenerationProgressEvent(
            generation_id=generation.id,
            status=GenerationStatus.DONE,
            progress=100,
            result_image_url="https://cdn.example/live.png",
        ).model_dump_json(),
    )
    await asyncio.sleep(0.05)
    second = None
    for _ in range(5):
        candidate = await asyncio.wait_for(anext(stream), timeout=2)
        if candidate["event"] == "result":
            second = candidate
            break
    assert second is not None
    assert json.loads(second["data"])["result_image_url"] == "https://cdn.example/live.png"

    await stream.aclose()
    await redis.aclose()


@pytest.mark.unit
async def test_conexao_apos_falha_emite_error_imediatamente() -> None:
    repo = InMemoryGenerationRepository()
    generation = _generation(GenerationStatus.FAILED)
    await repo.save(generation)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    stream = stream_generation_events(
        generation_id=generation.id,
        generations=repo,
        redis=redis,
        max_seconds=10,
    )
    event = await asyncio.wait_for(anext(stream), timeout=2)
    assert event["event"] == "error"
    assert json.loads(event["data"])["error"] == "falha"
    await stream.aclose()
    await redis.aclose()


@pytest.mark.unit
async def test_done_com_object_key_emite_url_assinada() -> None:
    from tests.conftest import InMemoryObjectStorage

    repo = InMemoryGenerationRepository()
    generation = _generation(GenerationStatus.PROCESSING)
    generation.result_object_key = f"generations/{generation.id}/result.png"
    await repo.save(generation)
    generation.transition_to(GenerationStatus.DONE)
    storage = InMemoryObjectStorage()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    stream = stream_generation_events(
        generation_id=generation.id,
        generations=repo,
        redis=redis,
        max_seconds=10,
        storage=storage,
    )
    event = await asyncio.wait_for(anext(stream), timeout=2)
    assert event["event"] == "result"
    payload = json.loads(event["data"])
    assert payload["result_image_url"].startswith("https://storage.test/")
    await stream.aclose()
    await redis.aclose()


@pytest.mark.unit
async def test_geracao_inexistente_emite_error() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    stream = stream_generation_events(
        generation_id=uuid4(),
        generations=InMemoryGenerationRepository(),
        redis=redis,
        max_seconds=10,
    )
    event = await asyncio.wait_for(anext(stream), timeout=2)
    assert event["event"] == "error"
    assert json.loads(event["data"])["error"] == "not_found"
    await stream.aclose()
    await redis.aclose()

@pytest.mark.unit
async def test_gauge_de_conexoes_sse_conta_entrada_e_saida() -> None:
    repo = InMemoryGenerationRepository()
    generation = _generation(GenerationStatus.PROCESSING)
    await repo.save(generation)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    stream = stream_generation_events(
        generation_id=generation.id,
        generations=repo,
        redis=redis,
        max_seconds=10,
    )
    before = REGISTRY.get_sample_value("aimaginator_sse_connections_active") or 0
    await asyncio.wait_for(anext(stream), timeout=2)
    assert REGISTRY.get_sample_value("aimaginator_sse_connections_active") == before + 1
    await stream.aclose()
    assert REGISTRY.get_sample_value("aimaginator_sse_connections_active") == before
    await redis.aclose()
