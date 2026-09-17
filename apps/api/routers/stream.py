"""SSE bridge: GET /api/v1/generations/{id}/stream (spec secao 13).

O worker Celery publica progresso no Redis Pub/Sub; este endpoint
apenas repassa (bridge) o canal para text/event-stream — qualquer
replica da API serve o stream, nao importa qual worker processou.

Autenticacao: EventSource nao suporta headers customizados, entao o
access token vem via query param `token` (com fallback para
Authorization/cookie). Encerra o stream quando chega evento terminal
(done/failed) ou apos o timeout maximo (evita conexoes eternas).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from apps.api.dependencies import (
    GenerationRepoDep,
    JWTDep,
    RedisDep,
    UserRepoDep,
    authenticate_user,
)
from modules.image_generation.application.ports import stream_channel
from modules.image_generation.contracts import GetGeneration

_MAX_STREAM_SECONDS = 600
_KEEPALIVE_SECONDS = 15

router = APIRouter(prefix="/api/v1", tags=["streaming"])


@router.get("/generations/{generation_id}/stream", include_in_schema=False)
async def stream_generation(
    generation_id: UUID,
    generations: GenerationRepoDep,
    redis: RedisDep,
    jwt: JWTDep,
    users: UserRepoDep,
    request: Request,
    token: str | None = Query(default=None),
) -> EventSourceResponse:
    # Valida ownership antes de abrir o stream (nao vaza canal a terceiros).
    user = await authenticate_user(request, jwt, users, query_token=token)
    await GetGeneration(generations).execute(user_id=user.id, generation_id=generation_id)

    async def event_generator() -> AsyncIterator[dict]:
        pubsub = redis.pubsub()
        await pubsub.subscribe(stream_channel(generation_id))
        try:
            deadline = asyncio.get_running_loop().time() + _MAX_STREAM_SECONDS
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    yield {"event": "error", "data": json.dumps({"error": "stream_timeout"})}
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=_KEEPALIVE_SECONDS
                )
                if message is None:
                    yield {"event": "ping", "data": "{}"}
                    continue

                payload = json.loads(message["data"])
                event_name = {
                    "queued": "status_update",
                    "processing": "progress",
                    "done": "result",
                    "failed": "error",
                }.get(payload.get("status"), "status_update")
                yield {"event": event_name, "data": json.dumps(payload)}
                if event_name in ("result", "error"):
                    break
        finally:
            await pubsub.unsubscribe(stream_channel(generation_id))
            await pubsub.aclose()

    return EventSourceResponse(event_generator())
