"""Health checks: /healthz (liveness) e /readyz (readiness com deps reais)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from apps.api.dependencies import RedisDep, SessionDep

router = APIRouter(tags=["ops"])


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(session: SessionDep, redis: RedisDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ready"}
