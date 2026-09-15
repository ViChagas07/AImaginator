"""Endpoint /metrics para scrape do Prometheus."""

from __future__ import annotations

from fastapi import APIRouter, Response

from modules.observability.metrics import render_metrics

router = APIRouter(tags=["ops"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")
