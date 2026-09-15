"""Testes do Circuit Breaker (fakeredis)."""

from __future__ import annotations

import pytest

from modules.rate_limiting.circuit_breaker import CircuitBreaker
from shared_kernel.errors import CircuitOpenError


async def _falha() -> None:
    raise ConnectionError("dependencia fora")


async def _ok() -> str:
    return "sucesso"


@pytest.mark.unit
async def test_fecha_circuito_em_sucesso(fake_redis) -> None:
    cb = CircuitBreaker(fake_redis, name="dep", failure_threshold=2, recovery_seconds=30)
    assert await cb.call(_ok) == "sucesso"


@pytest.mark.unit
async def test_abre_apos_threshold_de_falhas(fake_redis) -> None:
    cb = CircuitBreaker(fake_redis, name="dep", failure_threshold=2, recovery_seconds=30)
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await cb.call(_falha)
    # Circuito aberto: falha rapida SEM chamar a dependencia.
    with pytest.raises(CircuitOpenError):
        await cb.call(_ok)


@pytest.mark.unit
async def test_falha_abaixo_do_threshold_nao_abre(fake_redis) -> None:
    cb = CircuitBreaker(fake_redis, name="dep", failure_threshold=5, recovery_seconds=30)
    with pytest.raises(ConnectionError):
        await cb.call(_falha)
    assert await cb.call(_ok) == "sucesso"


@pytest.mark.unit
async def test_estado_compartilhado_entre_instancias(fake_redis) -> None:
    """Duas replicas (instancias) com mesmo Redis abrem o circuito juntas."""
    cb_a = CircuitBreaker(fake_redis, name="shared", failure_threshold=1, recovery_seconds=30)
    cb_b = CircuitBreaker(fake_redis, name="shared", failure_threshold=1, recovery_seconds=30)
    with pytest.raises(ConnectionError):
        await cb_a.call(_falha)
    with pytest.raises(CircuitOpenError):
        await cb_b.call(_ok)
