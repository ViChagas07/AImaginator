"""Porta de persistencia de geracoes."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.image_generation.domain.entities import Generation


class GenerationRepositoryPort(Protocol):
    async def get_by_id(self, generation_id: UUID) -> Generation | None: ...

    async def save(self, generation: Generation) -> Generation: ...

    async def delete(self, generation: Generation) -> None:
        """Soft delete (marca deleted_at)."""
        ...

    async def list_by_user(
        self, user_id: UUID, *, cursor: UUID | None, limit: int
    ) -> list[Generation]:
        """Paginacao por cursor (id), ordem decrescente de criacao."""
        ...

    async def list_by_anonymous_session(
        self, anonymous_session_id: str, *, limit: int
    ) -> list[Generation]:
        """Artes temporarias de uma sessao anonima (pre-login)."""
        ...

    async def reassign_anonymous_to_user(
        self, anonymous_session_id: str, user_id: UUID
    ) -> int:
        """Vincula artes anonimas a um usuario (pos-login). Devolve quantas migrou."""
        ...

    async def list_public_showcase(self, *, limit: int) -> list[Generation]:
        """Melhores geracoes concluidas (galeria publica/SEO)."""
        ...
