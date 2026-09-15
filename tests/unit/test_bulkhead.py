"""Testes do Bulkhead (isolamento de pools)."""

from __future__ import annotations

import asyncio

import pytest

from modules.rate_limiting.bulkhead import Bulkhead, BulkheadFullError, BulkheadRegistry


@pytest.mark.unit
async def test_isola_concorrencia_por_pool() -> None:
    lento = Bulkhead(name="lento", max_concurrent=1, max_queued=10)
    rapido = Bulkhead(name="rapido", max_concurrent=1, max_queued=10)
    ordem: list[str] = []

    async def tarefa_lenta() -> None:
        await asyncio.sleep(0.05)
        ordem.append("lento")

    async def tarefa_rapida() -> None:
        ordem.append("rapido")

    # Pool lento ocupado NAO bloqueia o pool rapido.
    await asyncio.gather(lento.run(tarefa_lenta), rapido.run(tarefa_rapida))
    assert ordem[0] == "rapido"


@pytest.mark.unit
async def test_fail_fast_quando_fila_cheia() -> None:
    pool = Bulkhead(name="p", max_concurrent=1, max_queued=1)

    async def bloqueante() -> None:
        await asyncio.sleep(0.05)

    async def cenario() -> None:
        primeira = asyncio.create_task(pool.run(bloqueante))
        await asyncio.sleep(0)  # garante que a primeira segurou o semaforo
        with pytest.raises(BulkheadFullError):
            await pool.run(bloqueante, fail_fast=True)
        await primeira

    await cenario()


@pytest.mark.unit
def test_registry_reutiliza_pools_nomeados() -> None:
    registry = BulkheadRegistry()
    a = registry.get_or_create("img_a", max_concurrent=2)
    b = registry.get_or_create("img_a", max_concurrent=99)
    assert a is b
