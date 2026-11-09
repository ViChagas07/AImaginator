"""Heartbeat do processo principal do worker (Redis, thread separada)."""

from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from datetime import UTC, datetime, timedelta

import redis as redis_sync

from modules.observability.logging_config import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "worker:heartbeat:"
_STATE_LOCK = threading.Lock()
_heartbeat: WorkerHeartbeat | None = None


class WorkerHeartbeat:
    def __init__(
        self,
        *,
        redis_client,
        worker_id: str,
        capabilities: tuple[str, ...],
        engine: str,
        ttl_seconds: int = 30,
        interval_seconds: float = 10.0,
        state: str = "idle",
        clock=None,
    ) -> None:
        self._redis = redis_client
        self.worker_id = worker_id
        self._capabilities = list(capabilities)
        self._engine = engine
        self._ttl = ttl_seconds
        self._interval = interval_seconds
        self._state = state
        self._reason: str | None = None
        self._cooling_until: datetime | None = None
        self._clock = clock or (lambda: datetime.now(UTC))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def key(self) -> str:
        return f"{_KEY_PREFIX}{self.worker_id}"

    def _effective_state(self) -> str:
        if (
            self._state == "cooling"
            and self._cooling_until is not None
            and self._clock() >= self._cooling_until
        ):
            self._state = "idle"
            self._reason = None
            self._cooling_until = None
        return self._state

    def payload(self) -> dict:
        with _STATE_LOCK:
            state = self._effective_state()
            payload = {
                "id": self.worker_id,
                "capabilities": self._capabilities,
                "engine": self._engine,
                "state": state,
                "reason": self._reason,
                "last_seen": self._clock().isoformat(),
                "host": socket.gethostname(),
            }
            if self._cooling_until is not None:
                payload["cooling_until"] = self._cooling_until.isoformat()
            return payload

    def beat(self) -> None:
        payload = self.payload()
        self._redis.setex(self.key, self._ttl, json.dumps(payload, separators=(",", ":")))

    def set_state(self, state: str, *, reason: str | None = None) -> None:
        with _STATE_LOCK:
            self._state = state
            self._reason = reason
            if state != "cooling":
                self._cooling_until = None
        self.beat()

    def set_cooling(self, seconds: int, *, reason: str) -> None:
        with _STATE_LOCK:
            self._state = "cooling"
            self._reason = reason
            self._cooling_until = self._clock() + timedelta(seconds=max(0, seconds))
        self.beat()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="worker-heartbeat", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self.beat()
            except Exception:
                logger.warning("worker_heartbeat_failed", exc_info=True)

    def stop(self) -> None:
        self._stop.set()
        try:
            self._redis.delete(self.key)
        except Exception:
            logger.warning("worker_heartbeat_delete_failed", exc_info=True)


def init_heartbeat(settings) -> WorkerHeartbeat:
    global _heartbeat
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    os.environ["AIMAGINATOR_WORKER_ID"] = worker_id
    client = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
    _heartbeat = WorkerHeartbeat(
        redis_client=client,
        worker_id=worker_id,
        capabilities=settings.worker_capability_list,
        engine=settings.image_engine,
        ttl_seconds=settings.worker_heartbeat_ttl_seconds,
        interval_seconds=settings.worker_heartbeat_interval_seconds,
    )
    _heartbeat.start()
    return _heartbeat


def get_heartbeat() -> WorkerHeartbeat | None:
    return _heartbeat


def mark_cooling(settings, seconds: int, reason: str) -> None:
    """Chamado no processo de tarefa; grava cooling para o worker atual."""
    worker_id = os.environ.get("AIMAGINATOR_WORKER_ID")
    if not worker_id:
        return
    client = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
    heartbeat = WorkerHeartbeat(
        redis_client=client,
        worker_id=worker_id,
        capabilities=settings.worker_capability_list,
        engine=settings.image_engine,
        ttl_seconds=settings.worker_heartbeat_ttl_seconds,
        interval_seconds=settings.worker_heartbeat_interval_seconds,
    )
    heartbeat.set_cooling(seconds, reason=reason)


def mark_state(settings, state: str, reason: str | None = None) -> None:
    worker_id = os.environ.get("AIMAGINATOR_WORKER_ID")
    if not worker_id:
        return
    client = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
    if state == "idle":
        raw = client.get(f"{_KEY_PREFIX}{worker_id}")
        if raw:
            try:
                current = json.loads(raw)
            except (TypeError, ValueError):
                current = {}
            if current.get("state") == "cooling":
                return
    heartbeat = WorkerHeartbeat(
        redis_client=client,
        worker_id=worker_id,
        capabilities=settings.worker_capability_list,
        engine=settings.image_engine,
        ttl_seconds=settings.worker_heartbeat_ttl_seconds,
        interval_seconds=settings.worker_heartbeat_interval_seconds,
    )
    heartbeat.set_state(state, reason=reason)


def stop_heartbeat() -> None:
    global _heartbeat
    if _heartbeat is not None:
        _heartbeat.stop()
        _heartbeat = None
