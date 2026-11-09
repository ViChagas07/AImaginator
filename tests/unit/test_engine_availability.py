"""Heartbeat de worker e disponibilidade do motor (sem Redis real)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from modules.image_generation.application.services.engine_availability import (
    EngineAvailabilityService,
)
from shared_kernel.security_errors import EngineOfflineError, MaintenanceError
from workers.celery_app.heartbeat import WorkerHeartbeat

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class _SyncRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def setex(self, key, ttl, value):
        self.data[key] = value
        self.ttls[key] = ttl

    def delete(self, key):
        self.data.pop(key, None)


class _AsyncRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key):
        return self.data.get(key)

    async def scan_iter(self, match=None):
        prefix = (match or "").rstrip("*")
        for key in list(self.data):
            if key.startswith(prefix):
                yield key


def _settings(**overrides):
    values = {
        "image_generation_enabled": True,
        "engine_availability_required": True,
        "image_engine": "sdcpp",
        "hosted_engine_configured": False,
        "maintenance_mode": False,
        "maintenance_redis_key": "system:maintenance",
        "worker_heartbeat_ttl_seconds": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _heartbeat(redis, clock=lambda: NOW) -> WorkerHeartbeat:
    return WorkerHeartbeat(
        redis_client=redis,
        worker_id="w1",
        capabilities=("generate", "edit"),
        engine="sdcpp",
        ttl_seconds=30,
        interval_seconds=10,
        clock=clock,
    )


@pytest.mark.unit
def test_heartbeat_publica_payload_com_ttl() -> None:
    redis = _SyncRedis()
    heartbeat = _heartbeat(redis)
    heartbeat.beat()

    payload = json.loads(redis.data[heartbeat.key])
    assert payload["id"] == "w1"
    assert payload["capabilities"] == ["generate", "edit"]
    assert payload["engine"] == "sdcpp"
    assert payload["state"] == "idle"
    assert payload["last_seen"].startswith("2026-01-01T12:00:00")
    assert redis.ttls[heartbeat.key] == 30


@pytest.mark.unit
def test_cooling_expira_para_idle_com_relogio_falso() -> None:
    now = NOW
    redis = _SyncRedis()
    heartbeat = WorkerHeartbeat(
        redis_client=redis,
        worker_id="w1",
        capabilities=("generate",),
        engine="sdcpp",
        clock=lambda: now,
    )
    heartbeat.set_cooling(60, reason="thermal_abort")
    assert json.loads(redis.data[heartbeat.key])["state"] == "cooling"

    now = NOW + timedelta(seconds=61)
    heartbeat.beat()
    assert json.loads(redis.data[heartbeat.key])["state"] == "idle"


@pytest.mark.unit
async def test_stub_esta_sempre_disponivel() -> None:
    service = EngineAvailabilityService(
        _AsyncRedis(), _settings(image_engine="stub"), clock=lambda: NOW
    )
    assert await service.available_kinds() == {
        "generate": True,
        "edit": True,
        "upscale": True,
    }


@pytest.mark.unit
async def test_sdcpp_sem_worker_fica_offline() -> None:
    service = EngineAvailabilityService(_AsyncRedis(), _settings(), clock=lambda: NOW)
    assert (await service.available_kinds())["generate"] is False
    with pytest.raises(EngineOfflineError):
        await service.ensure_available("generate", locale="en")


@pytest.mark.unit
async def test_worker_vivo_habilita_kind_e_cooling_desabilita() -> None:
    redis = _AsyncRedis()
    heartbeat = _heartbeat(_SyncRedis())
    redis.data[heartbeat.key] = json.dumps(heartbeat.payload())
    service = EngineAvailabilityService(redis, _settings(), clock=lambda: NOW)
    assert (await service.available_kinds())["generate"] is True
    assert (await service.available_kinds())["upscale"] is False

    redis.data[heartbeat.key] = json.dumps({**heartbeat.payload(), "state": "cooling"})
    assert (await service.available_kinds())["generate"] is False


@pytest.mark.unit
async def test_worker_antigo_e_ignorado_por_last_seen() -> None:
    redis = _AsyncRedis()
    heartbeat = _heartbeat(_SyncRedis())
    old = heartbeat.payload()
    old["last_seen"] = (NOW - timedelta(seconds=31)).isoformat()
    redis.data[heartbeat.key] = json.dumps(old)
    service = EngineAvailabilityService(redis, _settings(), clock=lambda: NOW)
    assert (await service.available_kinds())["generate"] is False


@pytest.mark.unit
async def test_manutencao_por_settings_e_override_redis() -> None:
    settings = _settings(maintenance_mode=True)
    service = EngineAvailabilityService(_AsyncRedis(), settings, clock=lambda: NOW)
    assert await service.maintenance() is True
    with pytest.raises(MaintenanceError):
        await service.ensure_available("generate")

    redis = _AsyncRedis()
    redis.data["system:maintenance"] = "0"
    service = EngineAvailabilityService(redis, _settings(), clock=lambda: NOW)
    assert await service.maintenance() is False


@pytest.mark.unit
async def test_status_publico_nao_expoe_workers() -> None:
    service = EngineAvailabilityService(_AsyncRedis(), _settings(), clock=lambda: NOW)
    status = await service.status()
    assert set(status) == {"feature_enabled", "maintenance", "available"}
    assert "worker" not in json.dumps(status).lower()
