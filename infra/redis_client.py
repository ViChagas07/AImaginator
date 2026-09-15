"""Cliente Redis async compartilhado (cache, pub/sub SSE, rate limiting)."""

from __future__ import annotations

import redis.asyncio as redis

from infra.settings import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Singleton do cliente Redis (pool interno gerenciado pela lib)."""
    global _client
    if _client is None:
        _client = redis.from_url(
            get_settings().redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
    return _client


def override_redis(client: redis.Redis) -> None:
    """Injeta cliente alternativo (testes com fakeredis)."""
    global _client
    _client = client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
