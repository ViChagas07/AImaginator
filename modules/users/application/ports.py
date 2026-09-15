"""Portas de saida do modulo users (direcao: application -> fora)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.users.domain.entities import User


class UserRepositoryPort(Protocol):
    """Contrato de persistencia de usuarios (implementado em adapters/)."""

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_google_sub(self, google_sub: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def save(self, user: User) -> User:
        """Upsert: cria ou atualiza pelo id."""
        ...
