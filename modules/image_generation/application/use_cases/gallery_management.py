"""Casos de uso de gestao da galeria pessoal (renomear, excluir, reivindicar)."""

from __future__ import annotations

from uuid import UUID

from modules.image_generation.application.ports import (
    GenerationRepositoryPort,
    ObjectStoragePort,
)
from modules.image_generation.application.schemas import GenerationOutput
from modules.image_generation.application.use_cases.read_generations import _to_output
from shared_kernel.errors import ForbiddenError, NotFoundError


class RenameGeneration:
    """Renomeia uma arte do usuario (valida ownership — anti-IDOR)."""

    def __init__(
        self, generations: GenerationRepositoryPort, *, storage: ObjectStoragePort | None = None
    ) -> None:
        self._generations = generations
        self._storage = storage

    async def execute(
        self,
        *,
        generation_id: UUID,
        title: str,
        user_id: UUID | None = None,
        anonymous_session_id: str | None = None,
    ) -> GenerationOutput:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError("Arte nao encontrada.")
        if not generation.belongs_to(
            user_id, anonymous_session_id=anonymous_session_id
        ):
            raise ForbiddenError("Acesso negado a esta arte.")
        generation.rename(title)
        await self._generations.save(generation)
        return await _to_output(generation, self._storage)


class DeleteGeneration:
    """Exclui (soft delete) uma arte do usuario (valida ownership)."""

    def __init__(self, generations: GenerationRepositoryPort) -> None:
        self._generations = generations

    async def execute(self, *, user_id: UUID, generation_id: UUID) -> None:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError("Arte nao encontrada.")
        if generation.user_id != user_id:
            raise ForbiddenError("Acesso negado a esta arte.")
        await self._generations.delete(generation)


class ClaimAnonymousArts:
    """Vincula as artes anonimas temporarias ao usuario recem-autenticado."""

    def __init__(self, generations: GenerationRepositoryPort) -> None:
        self._generations = generations

    async def execute(self, *, anonymous_session_id: str, user_id: UUID) -> int:
        return await self._generations.reassign_anonymous_to_user(
            anonymous_session_id, user_id
        )
