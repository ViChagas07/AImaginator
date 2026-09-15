"""Rate limiting por IP como middleware de borda (Token Bucket + Redis).

Limites por escopo de rota (auth e mais agressivo, spec secao 7).
Autenticados tambem passam por limite POR USUARIO dentro dos handlers.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from infra.redis_client import get_redis
from infra.settings import get_settings
from modules.rate_limiting.token_bucket import TokenBucket
from shared_kernel.errors import RateLimitExceededError

_IP_CAPACITY = 120  # req/min por IP (borda generica)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(("/healthz", "/readyz", "/metrics")):
            return await call_next(request)

        settings = get_settings()
        bucket = TokenBucket(get_redis(), capacity=_IP_CAPACITY, window_seconds=60)
        client_ip = request.client.host if request.client else "unknown"
        try:
            await bucket.consume(f"ip:{client_ip}")
        except RateLimitExceededError as exc:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(exc.retry_after_seconds)},
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        return await call_next(request)
