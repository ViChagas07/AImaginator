"""Ledger de creditos: idempotencia, concorrencia e reset mensal."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from modules.users.application.credits import CreditLedgerService
from modules.users.domain.entities import CreditLedgerEntry, User
from shared_kernel.errors import QuotaExceededError


class _Ledger:
    def __init__(self) -> None:
        self.entries: list[CreditLedgerEntry] = []

    async def get_by_idempotency_key(self, key):
        return next((e for e in self.entries if e.idempotency_key == key), None)

    async def add(self, entry):
        self.entries.append(entry)
        return entry


class _Users:
    def __init__(self, user: User, *, lock: asyncio.Lock | None = None) -> None:
        self.user = user
        self._lock = lock
        self._held = False

    async def get_by_id(self, user_id):
        return self.user

    async def get_by_id_for_update(self, user_id):
        if self._lock is not None:
            await self._lock.acquire()
            self._held = True
        return self.user

    async def save(self, user):
        if self._lock is not None and self._held:
            self._held = False
            self._lock.release()
        return user


def _service(users, ledger, *, now=None):
    return CreditLedgerService(
        users=users,
        ledger=ledger,
        monthly_credits=lambda plan: 50 if plan == "free" else 300,
        clock=lambda: now or datetime(2026, 2, 1, tzinfo=UTC),
    )


@pytest.mark.unit
async def test_consume_e_idempotente_por_chave() -> None:
    user = User(email="a@example.com", name="A")
    ledger = _Ledger()
    service = _service(_Users(user), ledger)

    await service.consume(
        user.id,
        ref_type="generation",
        ref_id="g1",
        idempotency_key="consume:g1",
    )
    await service.consume(
        user.id,
        ref_type="generation",
        ref_id="g1",
        idempotency_key="consume:g1",
    )
    assert user.generation_credits == 49
    assert len(ledger.entries) == 1


@pytest.mark.unit
async def test_refund_idempotente() -> None:
    user = User(email="a@example.com", name="A", generation_credits=49)
    ledger = _Ledger()
    service = _service(_Users(user), ledger)
    await service.refund(user.id, ref_type="generation", ref_id="g1", idempotency_key="refund:g1")
    await service.refund(user.id, ref_type="generation", ref_id="g1", idempotency_key="refund:g1")
    assert user.generation_credits == 50
    assert len(ledger.entries) == 1


@pytest.mark.unit
async def test_consumo_concorrente_nao_gera_saldo_negativo() -> None:
    user = User(email="a@example.com", name="A", generation_credits=1)
    ledger = _Ledger()
    lock = asyncio.Lock()
    service = _service(_Users(user, lock=lock), ledger)
    results = await asyncio.gather(
        service.consume(user.id, ref_type="generation", ref_id="g1", idempotency_key="c1"),
        service.consume(user.id, ref_type="generation", ref_id="g2", idempotency_key="c2"),
        return_exceptions=True,
    )
    assert user.generation_credits == 0
    assert sum(isinstance(r, QuotaExceededError) for r in results) == 1


@pytest.mark.unit
async def test_reset_mensal_idempotente() -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    user = User(
        email="a@example.com",
        name="A",
        generation_credits=7,
        credits_period_start=now - timedelta(days=40),
    )
    ledger = _Ledger()
    service = _service(_Users(user), ledger, now=now)
    await service.reset_if_due(user.id)
    await service.reset_if_due(user.id)
    assert user.generation_credits == 50
    assert len(ledger.entries) == 1
    assert ledger.entries[0].reason == "monthly_reset"


@pytest.mark.unit
async def test_admin_adjust_negativo_respeita_saldo() -> None:
    user = User(email="a@example.com", name="A", generation_credits=2)
    service = _service(_Users(user), _Ledger())
    await service.admin_adjust(user.id, delta=-2, idempotency_key="admin:1")
    assert user.generation_credits == 0
    with pytest.raises(QuotaExceededError):
        await service.admin_adjust(user.id, delta=-1, idempotency_key="admin:2")
