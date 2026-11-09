"""Ledger de creditos com saldo materializado e reset mensal idempotente."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.users.application.ports import (
    CreditLedgerRepositoryPort,
    UserRepositoryPort,
)
from modules.users.domain.entities import CreditLedgerEntry, User
from shared_kernel.errors import DomainError, QuotaExceededError

_REASONS = {"grant", "consume", "refund", "monthly_reset", "admin_adjust"}


class CreditLedgerService:
    def __init__(
        self,
        *,
        users: UserRepositoryPort,
        ledger: CreditLedgerRepositoryPort,
        monthly_credits: Callable[[str], int],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._users = users
        self._ledger = ledger
        self._monthly_credits = monthly_credits
        self._clock = clock or (lambda: datetime.now(UTC))

    async def reset_if_due(self, user_id: UUID) -> User:
        user = await self._users.get_by_id_for_update(user_id)
        if user is None:
            raise QuotaExceededError("Usuario nao encontrado.")
        now = self._clock()
        period = user.credits_period_start
        if (period.year, period.month) >= (now.year, now.month):
            return user
        month_key = f"{now.year:04d}-{now.month:02d}"
        target = self._monthly_credits(user.plan)
        entry = CreditLedgerEntry(
            user_id=user.id,
            delta=target - user.generation_credits,
            reason="monthly_reset",
            balance_after=target,
            idempotency_key=f"monthly:{user.id}:{month_key}",
            ref_type="plan",
            ref_id=user.plan,
        )
        if await self._ledger.get_by_idempotency_key(entry.idempotency_key):
            user.credits_period_start = now
            await self._users.save(user)
            return user
        user.generation_credits = target
        user.credits_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        user.updated_at = now
        await self._users.save(user)
        await self._ledger.add(entry)
        return user

    async def consume(
        self,
        user_id: UUID,
        *,
        amount: int = 1,
        ref_type: str,
        ref_id: str,
        idempotency_key: str,
        meta: dict | None = None,
    ) -> User:
        return await self._apply(
            user_id,
            delta=-abs(amount),
            reason="consume",
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=idempotency_key,
            meta=meta,
        )

    async def refund(
        self,
        user_id: UUID,
        *,
        amount: int = 1,
        ref_type: str,
        ref_id: str,
        idempotency_key: str,
        meta: dict | None = None,
    ) -> User:
        return await self._apply(
            user_id,
            delta=abs(amount),
            reason="refund",
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=idempotency_key,
            meta=meta,
        )

    async def grant(
        self,
        user_id: UUID,
        *,
        amount: int,
        idempotency_key: str,
        ref_type: str = "admin",
        ref_id: str | None = None,
        meta: dict | None = None,
    ) -> User:
        return await self._apply(
            user_id,
            delta=abs(amount),
            reason="grant",
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=idempotency_key,
            meta=meta,
        )

    async def admin_adjust(
        self,
        user_id: UUID,
        *,
        delta: int,
        idempotency_key: str,
        ref_id: str | None = None,
        meta: dict | None = None,
    ) -> User:
        return await self._apply(
            user_id,
            delta=delta,
            reason="admin_adjust",
            ref_type="admin",
            ref_id=ref_id,
            idempotency_key=idempotency_key,
            meta=meta,
        )

    async def _apply(
        self,
        user_id: UUID,
        *,
        delta: int,
        reason: str,
        ref_type: str | None,
        ref_id: str | None,
        idempotency_key: str,
        meta: dict | None,
    ) -> User:
        if reason not in _REASONS:
            raise DomainError("Motivo de credito invalido.")
        if await self._ledger.get_by_idempotency_key(idempotency_key):
            user = await self._users.get_by_id(user_id)
            if user is None:
                raise QuotaExceededError("Usuario nao encontrado.")
            return user

        user = await self._users.get_by_id_for_update(user_id)
        if user is None:
            raise QuotaExceededError("Usuario nao encontrado.")
        new_balance = user.generation_credits + delta
        if new_balance < 0:
            raise QuotaExceededError("Cota de geracoes esgotada.")
        user.generation_credits = new_balance
        user.updated_at = self._clock()
        await self._users.save(user)
        await self._ledger.add(
            CreditLedgerEntry(
                user_id=user.id,
                delta=delta,
                reason=reason,
                balance_after=new_balance,
                idempotency_key=idempotency_key,
                ref_type=ref_type,
                ref_id=ref_id,
                meta=meta,
                created_at=self._clock(),
            )
        )
        return user
