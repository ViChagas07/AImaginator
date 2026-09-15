"""Testes do Token Bucket distribuido (fakeredis)."""

from __future__ import annotations

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
def test_config_invalida_rejeitada() -> None:
    with pytest.raises(ValueError, match="positivos"):
        TokenBucket(object(), capacity=0, window_seconds=60)
