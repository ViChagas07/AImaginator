"""Eventos SSE resilientes: estado inicial do banco + Pub/Sub ao vivo."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from uuid import UUID

from modules.image_generation.application.ports import (
    GenerationRepositoryPort,
    ObjectStoragePort,
    stream_channel,
)
from modules.image_generation.application.schemas import GenerationProgressEvent
from modules.image_generation.domain.entities import Generation, GenerationStatus
from modules.observability.metrics import (
    SSE_CONNECTIONS_ACTIVE,
    SSE_STREAM_DURATION,
)

_EVENT_NAMES: dict[GenerationStatus, str] = {
    GenerationStatus.QUEUED: "status_update",
    GenerationStatus.PROCESSING: "progress",
    GenerationStatus.DONE: "result",
    GenerationStatus.FAILED: "error",
    GenerationStatus.CANCELED: "canceled",
}

_INITIAL_PROGRESS: dict[GenerationStatus, int] = {
    GenerationStatus.QUEUED: 0,
    GenerationStatus.PROCESSING: 5,
    GenerationStatus.DONE: 100,
    GenerationStatus.FAILED: 100,
    GenerationStatus.CANCELED: 100,
}

_INITIAL_STAGE: dict[GenerationStatus, str] = {
    GenerationStatus.QUEUED: "queued",
    GenerationStatus.PROCESSING: "processing",
    GenerationStatus.DONE: "done",
    GenerationStatus.FAILED: "failed",
    GenerationStatus.CANCELED: "canceled",
}


def event_name_for_status(status: GenerationStatus) -> str:
    return _EVENT_NAMES.get(status, "status_update")


def event_for_generation(generation: Generation) -> GenerationProgressEvent:
    """Monta o evento imediato a partir do estado persistido."""
    return GenerationProgressEvent(
        generation_id=generation.id,
        status=generation.status,
        progress=_INITIAL_PROGRESS[generation.status],
        stage=_INITIAL_STAGE[generation.status],
        result_image_url=(
            generation.result_image_url if generation.status == GenerationStatus.DONE else None
        ),
        seed=generation.seed,
        parent_generation_id=generation.parent_generation_id,
        error=(
            generation.error_message
            if generation.status in (GenerationStatus.FAILED, GenerationStatus.CANCELED)
            else None
        ),
        error_code=(
            generation.error_code
            if generation.status in (GenerationStatus.FAILED, GenerationStatus.CANCELED)
            else None
        ),
        warning_level=(
            generation.warning_level
            if generation.status in (GenerationStatus.FAILED, GenerationStatus.CANCELED)
            else None
        ),
        warning_message=(
            generation.warning_message
            if generation.status in (GenerationStatus.FAILED, GenerationStatus.CANCELED)
            else None
        ),
    )


def sse_event(event: GenerationProgressEvent) -> dict[str, str]:
    return {
        "event": event_name_for_status(event.status),
        "data": event.model_dump_json(),
    }


async def stream_generation_events(
    *,
    generation_id: UUID,
    generations: GenerationRepositoryPort,
    redis,
    max_seconds: int,
    keepalive_seconds: int = 15,
    storage: ObjectStoragePort | None = None,
) -> AsyncIterator[dict[str, str]]:
    started = time.monotonic()
    SSE_CONNECTIONS_ACTIVE.inc()
    try:
        async for event in _stream_generation_events(
            generation_id=generation_id,
            generations=generations,
            redis=redis,
            max_seconds=max_seconds,
            keepalive_seconds=keepalive_seconds,
            storage=storage,
        ):
            yield event
    finally:
        SSE_CONNECTIONS_ACTIVE.dec()
        SSE_STREAM_DURATION.observe(max(0.0, time.monotonic() - started))


async def _stream_generation_events(
    *,
    generation_id: UUID,
    generations: GenerationRepositoryPort,
    redis,
    max_seconds: int,
    keepalive_seconds: int = 15,
    storage: ObjectStoragePort | None = None,
) -> AsyncIterator[dict[str, str]]:
    """SSE: subscribe primeiro, emite estado atual e depois repassa o Pub/Sub.

    Assinar antes de ler o banco evita perder um evento publicado entre a
    leitura e a inscrição. Se a geracao ja terminou, o evento final e emitido
    imediatamente e o stream encerra.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(stream_channel(generation_id))
    try:
        generation = await generations.get_by_id(generation_id)
        if generation is None:
            yield {"event": "error", "data": json.dumps({"error": "not_found"})}
            return

        initial = event_for_generation(generation)
        if (
            storage is not None
            and generation.status == GenerationStatus.DONE
            and generation.result_object_key
        ):
            initial.result_image_url = await storage.presigned_get_url(
                generation.result_object_key
            )
        yield sse_event(initial)
        if initial.status in (
            GenerationStatus.DONE,
            GenerationStatus.FAILED,
            GenerationStatus.CANCELED,
        ):
            return

        deadline = asyncio.get_running_loop().time() + max_seconds
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                yield {"event": "error", "data": json.dumps({"error": "stream_timeout"})}
                return

            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=keepalive_seconds
            )
            if message is None:
                yield {"event": "ping", "data": "{}"}
                continue

            try:
                payload = json.loads(message["data"])
            except (TypeError, ValueError):
                continue

            event_name = _EVENT_NAMES.get(payload.get("status"), "status_update")
            yield {"event": event_name, "data": json.dumps(payload)}
            if event_name in ("result", "error", "canceled"):
                return
    finally:
        await pubsub.unsubscribe(stream_channel(generation_id))
        await pubsub.aclose()
