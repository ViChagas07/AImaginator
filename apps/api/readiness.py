"""Checagens de readiness (sem executar modelos)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from sqlalchemy import text

from infra.settings import Settings
from modules.image_generation.infra import wiring as gen_wiring


async def check_postgres(session) -> str:
    try:
        await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"


async def check_redis(redis) -> str:
    try:
        await redis.ping()
        return "ok"
    except Exception:
        return "unavailable"


async def check_rabbitmq(url: str) -> str:
    def _connect() -> None:
        from kombu import Connection

        with Connection(url, connect_timeout=2) as connection:
            connection.ensure_connection(max_retries=1)

    try:
        await asyncio.wait_for(asyncio.to_thread(_connect), timeout=3)
        return "ok"
    except Exception:
        return "unavailable"


async def check_s3(settings: Settings) -> str:
    if not settings.s3_bucket:
        return "skipped"
    storage = gen_wiring.build_object_storage(settings)
    if storage is None:
        return "unavailable"
    try:
        await storage.ensure_bucket()
        return "ok"
    except Exception:
        return "unavailable"


def check_sdcpp_files(settings: Settings) -> str:
    if settings.image_engine != "sdcpp":
        return "skipped"
    paths = (
        settings.sdcpp_binary_path,
        settings.sdcpp_vae_path,
        settings.sdcpp_clip_l_path,
        settings.sdcpp_t5xxl_path,
        settings.sdcpp_gen_model_path,
        settings.sdcpp_edit_model_path,
    )
    return "ok" if all(path and Path(path).is_file() for path in paths) else "missing"


async def check_lm_studio(
    settings: Settings, http_client: httpx.AsyncClient
) -> str:
    """Informativo: nunca derruba o readiness."""
    try:
        response = await http_client.get(
            f"{settings.llm_base_url.rstrip('/')}/models",
            timeout=httpx.Timeout(1.5, connect=1.0),
        )
        return "ok" if response.status_code < 500 else "unavailable"
    except Exception:
        return "unavailable"
