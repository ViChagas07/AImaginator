"""Stale-While-Revalidate — cache anti stampede (spec secao 10).

Envelope por chave:
  {"value": ..., "fresh_until": ts, "stale_until": ts}

- fresh  (agora < fresh_until)  -> devolve imediatamente.
- stale  (fresh_until <= agora < stale_until) -> devolve o valor velho
  IMEDIATAMENTE e dispara revalidacao em background protegida por lock
  SET NX (apenas 1 requisicao concorrente revalida — fim do stampede).
- ausente/expirado -> carrega de forma sincrona (com lock de dogpile),
  grava e devolve.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

_LOCK_TTL_SECONDS = 30


class SWRCache:
    def __init__(self, redis_client: Any, *, namespace: str = "swr") -> None:
        self._redis = redis_client
        self._ns = namespace

    def _key(self, key: str) -> str:
        return f"{self._ns}:{key}"

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Awaitable[T]],
        *,
        fresh_ttl_seconds: int = 60,
        stale_ttl_seconds: int = 300,
        on_background_error: Callable[[Exception], None] | None = None,
    ) -> T:
        now = time.time()
        raw = await self._redis.get(self._key(key))

        if raw:
            envelope = json.loads(raw)
            if now < envelope["fresh_until"]:
                return envelope["value"]
            if now < envelope["stale_until"]:
                await self._maybe_revalidate(
                    key, loader, fresh_ttl_seconds, stale_ttl_seconds, on_background_error
                )
                return envelope["value"]

        value = await loader()
        await self._store(key, value, fresh_ttl_seconds, stale_ttl_seconds)
        return value

    async def _maybe_revalidate(
        self,
        key: str,
        loader: Callable[[], Awaitable[T]],
        fresh_ttl: int,
        stale_ttl: int,
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        lock_key = f"{self._key(key)}:lock"
        acquired = await self._redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL_SECONDS)
        if not acquired:
            return  # outra replica/request ja esta revalidando

        async def _revalidate() -> None:
            try:
                value = await loader()
                await self._store(key, value, fresh_ttl, stale_ttl)
            except Exception as exc:  # noqa: BLE001 — background: engolir e reportar
                if on_error:
                    on_error(exc)
            finally:
                await self._redis.delete(lock_key)

        asyncio.get_running_loop().create_task(_revalidate())

    async def _store(self, key: str, value: T, fresh_ttl: int, stale_ttl: int) -> None:
        now = time.time()
        envelope = {
            "value": value,
            "fresh_until": now + fresh_ttl,
            "stale_until": now + stale_ttl,
        }
        await self._redis.set(self._key(key), json.dumps(envelope), ex=stale_ttl + 60)

    async def invalidate(self, key: str) -> None:
        await self._redis.delete(self._key(key))
