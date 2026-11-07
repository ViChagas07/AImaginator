"""Health checks: /healthz (liveness) e /readyz (readiness com deps reais)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apps.api.dependencies import RedisDep, SessionDep, SettingsDep
from apps.api.readiness import (
    check_lm_studio,
    check_postgres,
    check_rabbitmq,
    check_redis,
    check_s3,
    check_sdcpp_files,
)

router = APIRouter(tags=["ops"])


@router.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> JSONResponse:
    checks = {
        "postgres": await check_postgres(session),
        "redis": await check_redis(redis),
        "rabbitmq": await check_rabbitmq(settings.celery_broker_url),
        "s3": await check_s3(settings),
        "sdcpp": check_sdcpp_files(settings),
    }
    warnings: dict[str, str] = {}
    try:
        warnings["lm_studio"] = await check_lm_studio(
            settings, request.app.state.http_client
        )
    except Exception:
        warnings["lm_studio"] = "unavailable"
    blocking = {
        name: status
        for name, status in checks.items()
        if status not in ("ok", "skipped")
    }
    payload = {
        "status": "ready" if not blocking else "not_ready",
        "checks": checks,
        "warnings": warnings,
    }
    return JSONResponse(status_code=200 if not blocking else 503, content=payload)
