"""Testes do Token Bucket distribuido (fakeredis)."""

from __future__ import annotations

import time

import pytest

from modules.rate_limiting.token_bucket import TokenBucket
from shared_kernel.errors import RateLimitExceededError


@pytest.mark.unit
async def test_permite_ate_a_capacidade(fake_redis) -> None:
    bucket = TokenBucket(fake_redis, capacity=3, window_seconds=60)
    for _ in range(3):
        await bucket.consume("user:1")  # nao levanta


@pytest.mark.unit
async def test_bloqueia_ao_estourar_capacidade(fake_redis) -> None:
    bucket = TokenBucket(fake_redis, capacity=2, window_seconds=60)
    await bucket.consume("user:1")
    await bucket.consume("user:1")
    with pytest.raises(RateLimitExceededError) as exc_info:
        await bucket.consume("user:1")
    assert exc_info.value.retry_after_seconds >= 1


@pytest.mark.unit
async def test_baldes_independentes_por_chave(fake_redis) -> None:
    bucket = TokenBucket(fake_redis, capacity=1, window_seconds=60)
    await bucket.consume("user:1")
    await bucket.consume("user:2")  # chave diferente: permitido
    with pytest.raises(RateLimitExceededError):
        await bucket.consume("user:1")


@pytest.mark.unit
async def test_try_consume_nao_levanta(fake_redis) -> None:
    bucket = TokenBucket(fake_redis, capacity=1, window_seconds=60)
    assert await bucket.try_consume("k") is True
    assert await bucket.try_consume("k") is False


@pytest.mark.unit
async def test_relogio_local_divergente_nao_afeta_redis(
    fake_redis, monkeypatch
) -> None:
    bucket = TokenBucket(fake_redis, capacity=1, window_seconds=60)
    await bucket.consume("user:clock")
    monkeypatch.setattr(time, "monotonic", lambda: 10**12)
    with pytest.raises(RateLimitExceededError):
        await bucket.consume("user:clock")


@pytest.mark.unit
async def test_nao_reutiliza_estado_legado_de_balde(fake_redis) -> None:
    # Versoes antigas gravavam "tb:{chave}" com time.monotonic(). O namespace
    # novo deve ignorar esse estado, que pode estar negativo apos um restart.
    await fake_redis.hset(
        "tb:ip:legacy", mapping={"tokens": -10_000_000, "ts": 1}
    )
    bucket = TokenBucket(fake_redis, capacity=1, window_seconds=60)

    await bucket.consume("ip:legacy")


@pytest.mark.unit
def test_config_invalida_rejeitada() -> None:
    with pytest.raises(ValueError, match="positivos"):
        TokenBucket(object(), capacity=0, window_seconds=60)
