"""Porta de persistencia de geracoes."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.image_generation.domain.entities import Generation


class GenerationRepositoryPort(Protocol):
    async def get_by_id(self, generation_id: UUID) -> Generation | None: ...

    async def save(self, generation: Generation) -> Generation: ...

    async def list_by_user(
        self, user_id: UUID, *, cursor: UUID | None, limit: int
    ) -> list[Generation]:
        """Paginacao por cursor (id), ordem decrescente de criacao."""
        ...

    async def list_public_showcase(self, *, limit: int) -> list[Generation]:
        """Melhores geracoes concluidas (galeria publica/SEO)."""
        ...
