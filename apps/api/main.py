"""Composicao da API FastAPI — outermost layer (frameworks & drivers).

Responsabilidades: lifespan (engine Redis/HTTP up/down), middlewares,
routers, exception handlers que mapeiam erros de dominio para HTTP
sem vazar stack traces ao cliente (detalhes so no Sentry).
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.middlewares.metrics import MetricsMiddleware
from apps.api.middlewares.payload_limit import PayloadLimitMiddleware
from apps.api.middlewares.rate_limit import RateLimitMiddleware
from apps.api.middlewares.security_headers import SecurityHeadersMiddleware
from apps.api.routers import (
    auth,
    gallery,
    generations,
    health,
    metrics,
    prompt_quota,
    stream,
    users,
)
from infra.database import dispose_engine
from infra.redis_client import close_redis
from infra.settings import get_settings
from modules.observability.logging_config import configure_logging, get_logger
from modules.observability.sentry_setup import init_sentry
from shared_kernel.errors import AImaginatorError

logger = get_logger(__name__)

# Raiz do repositorio (onde ficam alembic.ini e alembic/), resolvida a partir
# deste arquivo: apps/api/main.py -> apps -> raiz.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_pending_migrations() -> None:
    """Aplica migrations pendentes (alembic upgrade head) antes de servir.

    Roda em subprocesso para isolar o event loop: o alembic/env.py chama
    asyncio.run(), que nao pode rodar dentro do loop do FastAPI. Falhas sao
    logadas (nao derrubam o boot) para nao criar crash loop no provedor.
    """
    try:
        result = subprocess.run(  # noqa: S603 - comando fixo (alembic), sem input externo
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        logger.error("migrations_failed", error=type(exc).__name__, message=str(exc))
        return
    if result.returncode != 0:
        logger.error(
            "migrations_failed",
            returncode=result.returncode,
            stderr=result.stderr[-2000:],
        )
        return
    logger.info("migrations_ok", output=(result.stdout.strip() or "")[-500:])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    configure_logging(app_env=settings.app_env)
    init_sentry(dsn=settings.sentry_dsn_backend, environment=settings.sentry_environment)
    if settings.auto_migrate:
        await asyncio.to_thread(_run_pending_migrations)
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
    )
    logger.info("api_started", env=settings.app_env)
    yield
    await app.state.http_client.aclose()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AImaginator API",
        version="0.1.0",
        description="API de geracao e edicao de imagens via IA.",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Middlewares (ordem: o mais externo primeiro).
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(PayloadLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Anonymous-Session"],
    )

    # Routers.
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(generations.router)
    app.include_router(stream.router)
    app.include_router(gallery.router)
    app.include_router(prompt_quota.router)
    app.include_router(users.router)

    @app.exception_handler(AImaginatorError)
    async def domain_error_handler(request: Request, exc: AImaginatorError) -> JSONResponse:
        headers = {}
        retry_after = getattr(exc, "retry_after_seconds", None)
        if exc.http_status == 429 and retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        return JSONResponse(
            status_code=exc.http_status,
            headers=headers,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Nunca vazar stack trace ao cliente — so ao Sentry/logs (spec secao 7).
        logger.exception(
            "unhandled_error",
            path=request.url.path,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Erro interno."}},
        )

    return app


app = create_app()
