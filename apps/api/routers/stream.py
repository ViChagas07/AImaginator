"""SSE bridge: ticket efemero de uso unico (nunca JWT na URL).

Fluxo:
1. POST /generations/{id}/stream-ticket (auth ou sessao anonima) valida
   ownership e grava um ticket aleatorio no Redis com TTL curto.
2. GET /generations/{id}/stream?ticket=... consome o ticket (single-use) e
   abre o EventSourceResponse.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sse_starlette.sse import EventSourceResponse

from apps.api.dependencies import (
    GenerationRepoDep,
    ObjectStorageDep,
    OptionalCurrentUserDep,
    QueueReconcilerDep,
    RedisDep,
    SettingsDep,
    StreamTicketDep,
    get_generation_rate_limiter,
    resolve_anonymous_session,
    set_anonymous_session_cookie,
)
from modules.image_generation.application.stream_events import stream_generation_events
from modules.image_generation.application.stream_policy import stream_timeout_seconds
from modules.rate_limiting.token_bucket import TokenBucket
from shared_kernel.errors import ForbiddenError, NotFoundError, UnauthorizedError

_KEEPALIVE_SECONDS = 15

router = APIRouter(prefix="/api/v1", tags=["streaming"])


@router.post("/generations/{generation_id}/stream-ticket", include_in_schema=False)
async def issue_stream_ticket(
    generation_id: UUID,
    request: Request,
    response: Response,
    current_user: OptionalCurrentUserDep,
    generations: GenerationRepoDep,
    settings: SettingsDep,
    tickets: StreamTicketDep,
    reconciler: QueueReconcilerDep,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> dict:
    generation = await generations.get_by_id(generation_id)
    if generation is None:
        raise NotFoundError("Geracao nao encontrada.")

    if current_user is not None:
        if generation.user_id != current_user.id:
            raise ForbiddenError("Acesso negado a esta geracao.")
        principal = f"user:{current_user.id}"
        user_id = current_user.id
        anonymous_id = None
    else:
        anonymous_id, token = resolve_anonymous_session(request, settings)
        set_anonymous_session_cookie(response, settings, token)
        if generation.user_id is not None or generation.anonymous_session_id != anonymous_id:
            raise ForbiddenError("Acesso negado a esta geracao.")
        principal = f"anon:{anonymous_id}"
        user_id = None

    await limiter.consume(f"stream-ticket:{principal}")
    await reconciler.reconcile_generation(generation.id)
    ticket = await tickets.issue(
        generation_id=generation.id,
        user_id=user_id,
        anonymous_session_id=anonymous_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "ticket": ticket,
        "stream_url": f"/api/v1/generations/{generation.id}/stream",
        "expires_in": settings.stream_ticket_ttl_seconds,
    }


@router.get("/generations/{generation_id}/stream", include_in_schema=False)
async def stream_generation(
    generation_id: UUID,
    generations: GenerationRepoDep,
    redis: RedisDep,
    settings: SettingsDep,
    storage: ObjectStorageDep,
    tickets: StreamTicketDep,
    reconciler: QueueReconcilerDep,
    ticket: str = Query(..., min_length=16, max_length=256),
) -> EventSourceResponse:
    principal = await tickets.redeem(ticket)
    if principal is None:
        raise UnauthorizedError("Ticket de stream invalido ou expirado.")
    if principal.generation_id != generation_id:
        raise ForbiddenError("Ticket nao pertence a esta geracao.")
    if await generations.get_by_id(generation_id) is None:
        raise NotFoundError("Geracao nao encontrada.")
    await reconciler.reconcile_generation(generation_id)

    return EventSourceResponse(
        stream_generation_events(
            generation_id=generation_id,
            generations=generations,
            redis=redis,
            max_seconds=stream_timeout_seconds(settings),
            keepalive_seconds=_KEEPALIVE_SECONDS,
            storage=storage,
        ),
        headers={"Cache-Control": "no-store"},
    )
