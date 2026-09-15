"""Testes do cache SWR anti stampede (fakeredis)."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from modules.image_generation.adapters.cache.swr import SWRCache


@pytest.mark.unit
async def test_miss_carrega_e_cacheia(fake_redis) -> None:
    cache = SWRCache(fake_redis)
    chamadas = 0

    async def loader() -> dict:
        nonlocal chamadas
        chamadas += 1
        return {"valor": 42}

    assert await cache.get_or_load("k", loader) == {"valor": 42}
    assert await cache.get_or_load("k", loader) == {"valor": 42}
    assert chamadas == 1  # segundo hit veio do cache


@pytest.mark.unit
async def test_stale_devolve_velho_e_revalida_em_background(fake_redis) -> None:
    cache = SWRCache(fake_redis)
    envelope = {
        "value": {"valor": "velho"},
        "fresh_until": time.time() - 1,      # passou do fresh
        "stale_until": time.time() + 300,    # ainda valido (stale)
    }
    await fake_redis.set("swr:k", json.dumps(envelope))

    async def loader() -> dict:
        await asyncio.sleep(0)
        return {"valor": "novo"}

    # Devolve o stale IMEDIATAMENTE...
    assert await cache.get_or_load("k", loader) == {"valor": "velho"}
    await asyncio.sleep(0.05)  # deixa a revalidacao background rodar
    # ...e a proxima leitura ja ve o valor novo.
    assert await cache.get_or_load("k", loader) == {"valor": "novo"}


@pytest.mark.unit
async def test_lock_impede_stampede_de_revalidacao(fake_redis) -> None:
    cache = SWRCache(fake_redis)
    envelope = {
        "value": "stale",
        "fresh_until": time.time() - 1,
        "stale_until": time.time() + 300,
    }
    await fake_redis.set("swr:k", json.dumps(envelope))
    chamadas = 0

    async def loader_lento() -> str:
        nonlocal chamadas
        chamadas += 1
        await asyncio.sleep(0.05)
        return "novo"

    # 10 requisicoes concorrentes no dado stale: apenas UMA revalida.
    await asyncio.gather(*(cache.get_or_load("k", loader_lento) for _ in range(10)))
    await asyncio.sleep(0.15)
    assert chamadas == 1


@pytest.mark.unit
async def test_expirado_total_recarrega_sincrono(fake_redis) -> None:
    cache = SWRCache(fake_redis)
    envelope = {
        "value": "morto",
        "fresh_until": time.time() - 400,
        "stale_until": time.time() - 300,
    }
    await fake_redis.set("swr:k", json.dumps(envelope))

    async def loader() -> str:
        return "reavivado"

    assert await cache.get_or_load("k", loader) == "reavivado"


@pytest.mark.unit
async def test_erro_background_nao_derruba_request(fake_redis) -> None:
    cache = SWRCache(fake_redis)
    envelope = {
        "value": "stale-ok",
        "fresh_until": time.time() - 1,
        "stale_until": time.time() + 300,
    }
    await fake_redis.set("swr:k", json.dumps(envelope))
    erros: list[Exception] = []

    async def loader_falho() -> str:
        raise RuntimeError("backend fora")

    valor = await cache.get_or_load("k", loader_falho, on_background_error=erros.append)
    assert valor == "stale-ok"  # request sai com o stale mesmo assim
    await asyncio.sleep(0.05)
    assert len(erros) == 1
