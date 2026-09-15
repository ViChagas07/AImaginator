"""Circuit Breaker para chamadas a servicos externos instaveis.

Estados: CLOSED (normal) -> OPEN (falha rapida, nao chama a dependencia)
-> HALF_OPEN (probing periodico). Estado compartilhado via Redis para
que todas as replicas abram o circuito juntas.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from shared_kernel.errors import CircuitOpenError

T = TypeVar("T")

_CLOSED = "closed"
_OPEN = "open"
_HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        redis_client,
        *,
        name: str,
        failure_threshold: int = 5,
        recovery_seconds: int = 30,
    ) -> None:
        self._redis = redis_client
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._key = f"cb:{name}"

    async def _state(self) -> str:
        data = await self._redis.hgetall(self._key)
        if not data:
            return _CLOSED
        state = data.get("state", _CLOSED)
        if state == _OPEN:
            opened_at = float(data.get("opened_at", 0))
            if time.monotonic() - opened_at >= self.recovery_seconds:
                return _HALF_OPEN
        return state

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Executa fn protegido pelo circuito. Falha rapida se OPEN."""
        state = await self._state()
        if state == _OPEN:
            raise CircuitOpenError(
                f"Dependencia '{self.name}' temporariamente indisponivel (circuito aberto)."
            )
        try:
            result = await fn()
        except Exception:
            await self._record_failure()
            raise
        await self._record_success()
        return result

    async def _record_failure(self) -> None:
        failures = await self._redis.hincrby(self._key, "failures", 1)
        if failures >= self.failure_threshold:
            await self._redis.hset(
                self._key,
                mapping={"state": _OPEN, "opened_at": time.monotonic(), "failures": 0},
            )
        await self._redis.expire(self._key, self.recovery_seconds * 4)

    async def _record_success(self) -> None:
        # Half-open com sucesso (ou operacao normal): fecha o circuito.
        await self._redis.hset(self._key, mapping={"state": _CLOSED, "failures": 0})
