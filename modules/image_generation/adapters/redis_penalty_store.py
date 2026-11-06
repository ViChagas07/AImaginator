"""Store Redis de bloqueios temporarios de moderacao (anonimos e IP)."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime

from modules.image_generation.application.ports.moderation import PenaltyStorePort


class RedisPenaltyStore(PenaltyStorePort):
    def __init__(self, redis_client, *, namespace: str = "moderation") -> None:
        self._redis = redis_client
        self._namespace = namespace

    def _key(self, key: str) -> str:
        return f"{self._namespace}:block:{key}"

    async def get_block_until(self, *, keys: Sequence[str]) -> datetime | None:
        latest: float | None = None
        for key in keys:
            raw = await self._redis.get(self._key(key))
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > time.time() and (latest is None or value > latest):
                latest = value
        return datetime.fromtimestamp(latest, UTC) if latest else None

    async def set_block(self, *, keys: Sequence[str], until: datetime) -> None:
        ttl = max(1, int(until.timestamp() - time.time()))
        for key in keys:
            await self._redis.set(self._key(key), str(until.timestamp()), ex=ttl)
