"""Instrumentacao Prometheus por request (latencia + contagem + status)."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from modules.observability.metrics import HTTP_REQUEST_LATENCY, HTTP_REQUESTS_TOTAL


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        endpoint = request.scope.get("route")
        path = endpoint.path if endpoint else request.url.path
        labels = {"method": request.method, "endpoint": path}
        HTTP_REQUEST_LATENCY.labels(**labels).observe(elapsed)
        HTTP_REQUESTS_TOTAL.labels(**labels, status=str(response.status_code)).inc()
        return response
