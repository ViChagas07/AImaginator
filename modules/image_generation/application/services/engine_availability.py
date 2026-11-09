"""Disponibilidade do motor: workers vivos, manutencao e status publico."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from modules.image_generation.application.localization import message_for
from shared_kernel.security_errors import EngineOfflineError, MaintenanceError

_KINDS = ("generate", "edit", "upscale")


class EngineAvailabilityService:
    def __init__(self, redis, settings, *, clock: Callable[[], datetime] | None = None):
        self._redis = redis
        self._settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))

    async def maintenance(self) -> bool:
        override = await self._redis.get(self._settings.maintenance_redis_key)
        if override is not None:
            if isinstance(override, bytes):
                override = override.decode("utf-8", errors="replace")
            return str(override).strip().lower() in {"1", "true", "on", "yes"}
        return bool(self._settings.maintenance_mode)

    async def workers(self) -> list[dict]:
        workers: list[dict] = []
        cutoff = self._clock() - timedelta(seconds=self._settings.worker_heartbeat_ttl_seconds)
        async for key in self._redis.scan_iter(match="worker:heartbeat:*"):
            raw = await self._redis.get(key)
            if not raw:
                continue
            try:
                import json

                payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            except (ValueError, TypeError):
                continue
            last_seen = payload.get("last_seen")
            try:
                seen_at = datetime.fromisoformat(str(last_seen))
            except (TypeError, ValueError):
                continue
            if seen_at.tzinfo is None:
                seen_at = seen_at.replace(tzinfo=UTC)
            if seen_at < cutoff:
                continue
            workers.append(payload)
        return workers

    async def available_kinds(self) -> dict[str, bool]:
        if not self._settings.image_generation_enabled:
            return {kind: False for kind in _KINDS}
        if not self._settings.engine_availability_required:
            return {kind: True for kind in _KINDS}
        if self._settings.image_engine == "hosted":
            ok = self._settings.hosted_engine_configured
            return {kind: ok for kind in _KINDS}
        if self._settings.image_engine == "stub":
            return {kind: True for kind in _KINDS}
        workers = await self.workers()
        available: dict[str, bool] = {}
        for kind in _KINDS:
            available[kind] = any(
                kind in (worker.get("capabilities") or []) and worker.get("state") != "cooling"
                for worker in workers
            )
        return available

    async def ensure_available(self, kind: str, *, locale: str = "pt-BR") -> None:
        if await self.maintenance():
            raise MaintenanceError(message_for("maintenance", locale))
        available = await self.available_kinds()
        if not available.get(kind, False):
            raise EngineOfflineError(message_for("engine_offline", locale))

    async def status(self) -> dict:
        available = await self.available_kinds()
        return {
            "feature_enabled": bool(self._settings.image_generation_enabled),
            "maintenance": await self.maintenance(),
            "available": available,
        }
