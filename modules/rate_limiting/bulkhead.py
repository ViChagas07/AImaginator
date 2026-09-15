"""Bulkhead: isolamento de pools de recursos por dependencia/classe de carga.

Evita que uma dependencia lenta (ex.: provedor de imagem A) esgote os
recursos e derrube o resto do sistema. Cada bulkhead tem seu proprio
semaforo: quem excede a capacidade espera apenas naquela fila, sem
bloquear os demais pools.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class BulkheadFullError(Exception):
    """Pool saturado e sem fila de espera disponivel (fail-fast)."""


class Bulkhead:
    def __init__(self, *, name: str, max_concurrent: int, max_queued: int = 100) -> None:
        if max_concurrent <= 0:
            msg = "max_concurrent deve ser positivo"
            raise ValueError(msg)
        self.name = name
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_queued = max_queued
        self._queued = 0

    @property
    def available(self) -> bool:
        return self._semaphore._value > 0 or self._queued < self._max_queued  # noqa: SLF001

    async def run(self, fn: Callable[[], Awaitable[T]], *, fail_fast: bool = False) -> T:
        if fail_fast and self._queued >= self._max_queued:
            raise BulkheadFullError(f"Bulkhead '{self.name}' saturado.")
        self._queued += 1
        try:
            async with self._semaphore:
                return await fn()
        finally:
            self._queued -= 1


class BulkheadRegistry:
    """Registro nomeado de bulkheads (um pool por dependencia externa)."""

    def __init__(self) -> None:
        self._pools: dict[str, Bulkhead] = {}

    def get_or_create(self, name: str, *, max_concurrent: int, max_queued: int = 100) -> Bulkhead:
        if name not in self._pools:
            self._pools[name] = Bulkhead(
                name=name, max_concurrent=max_concurrent, max_queued=max_queued
            )
        return self._pools[name]


bulkhead_registry = BulkheadRegistry()
