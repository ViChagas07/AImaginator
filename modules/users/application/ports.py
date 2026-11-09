"""Portas de saida do modulo users (direcao: application -> fora)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from modules.users.domain.entities import CreditLedgerEntry, User, UserSettings


class UserRepositoryPort(Protocol):
    """Contrato de persistencia de usuarios (implementado em adapters/)."""

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_id_for_update(self, user_id: UUID) -> User | None:
        """SELECT ... FOR UPDATE para operacoes de saldo/cota."""
        ...

    async def get_by_google_sub(self, google_sub: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_handle(self, handle: str) -> User | None: ...

    async def save(self, user: User) -> User:
        """Upsert: cria ou atualiza pelo id."""
        ...

    async def get_settings(self, user_id: UUID) -> UserSettings | None: ...

    async def save_settings(self, settings: UserSettings) -> UserSettings:
        """Upsert: cria ou atualiza as configuracoes do usuario."""
        ...

    async def list_flagged(self, *, limit: int = 100) -> list[User]: ...

    async def list_period_due(
        self, *, before: datetime, limit: int = 1000
    ) -> list[User]: ...


class CreditLedgerRepositoryPort(Protocol):
    async def get_by_idempotency_key(
        self, key: str
    ) -> CreditLedgerEntry | None: ...

    async def add(self, entry: CreditLedgerEntry) -> CreditLedgerEntry: ...
