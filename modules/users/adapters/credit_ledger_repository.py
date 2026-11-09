"""Persistencia SQLAlchemy do ledger de creditos."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.users.adapters.models import CreditLedgerModel
from modules.users.application.ports import CreditLedgerRepositoryPort
from modules.users.domain.entities import CreditLedgerEntry


class SQLAlchemyCreditLedgerRepository(CreditLedgerRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(self, key: str) -> CreditLedgerEntry | None:
        stmt = select(CreditLedgerModel).where(CreditLedgerModel.idempotency_key == key)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        return CreditLedgerEntry(
            id=model.id,
            user_id=model.user_id,
            delta=model.delta,
            reason=model.reason,
            ref_type=model.ref_type,
            ref_id=model.ref_id,
            idempotency_key=model.idempotency_key,
            balance_after=model.balance_after,
            meta=model.meta,
            created_at=model.created_at,
        )

    async def add(self, entry: CreditLedgerEntry) -> CreditLedgerEntry:
        model = CreditLedgerModel(
            id=entry.id,
            user_id=entry.user_id,
            delta=entry.delta,
            reason=entry.reason,
            ref_type=entry.ref_type,
            ref_id=entry.ref_id,
            idempotency_key=entry.idempotency_key,
            balance_after=entry.balance_after,
            meta=entry.meta,
            created_at=entry.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return entry
