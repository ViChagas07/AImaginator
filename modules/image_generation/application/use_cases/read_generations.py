"""Casos de uso de leitura: detalhe (com ownership) e historico paginado."""

from __future__ import annotations

import base64
from uuid import UUID

from modules.image_generation.application.ports import GenerationRepositoryPort
from modules.image_generation.application.schemas import GenerationOutput, GenerationPage
from modules.image_generation.domain.entities import Generation
from shared_kernel.errors import ForbiddenError, NotFoundError

_STREAM_PATH = "/api/v1/generations/{id}/stream"
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 50


def _to_output(generation: Generation) -> GenerationOutput:
    return GenerationOutput(
        id=generation.id,
        kind=generation.kind,
        status=generation.status,
        prompt=generation.prompt,
        style_preset=generation.style_preset,
        aspect_ratio=generation.aspect_ratio,
        result_image_url=generation.result_image_url,
        error_message=generation.error_message,
        created_at=generation.created_at,
        completed_at=generation.completed_at,
        stream_url=_STREAM_PATH.format(id=generation.id),
    )


class GetGeneration:
    def __init__(self, generations: GenerationRepositoryPort) -> None:
        self._generations = generations

    async def execute(self, *, user_id: UUID, generation_id: UUID) -> GenerationOutput:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError("Geracao nao encontrada.")
        if generation.user_id != user_id:
            # Nao vaza existencia do recurso a terceiros (anti-enumeracao).
            raise ForbiddenError("Acesso negado a esta geracao.")
        return _to_output(generation)


class ListUserGenerations:
    def __init__(self, generations: GenerationRepositoryPort) -> None:
        self._generations = generations

    async def execute(
        self, *, user_id: UUID, cursor: str | None, limit: int = _DEFAULT_PAGE_SIZE
    ) -> GenerationPage:
        limit = max(1, min(limit, _MAX_PAGE_SIZE))
        cursor_uuid = self._decode_cursor(cursor)
        items = await self._generations.list_by_user(user_id, cursor=cursor_uuid, limit=limit + 1)
        next_cursor = None
        if len(items) > limit:
            items = items[:limit]
            next_cursor = self._encode_cursor(items[-1].id)
        return GenerationPage(items=[_to_output(g) for g in items], next_cursor=next_cursor)

    @staticmethod
    def _encode_cursor(generation_id: UUID) -> str:
        return base64.urlsafe_b64encode(str(generation_id).encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str | None) -> UUID | None:
        if not cursor:
            return None
        try:
            return UUID(base64.urlsafe_b64decode(cursor.encode()).decode())
        except (ValueError, UnicodeDecodeError) as exc:
            from shared_kernel.errors import DomainError

            raise DomainError("Cursor de paginacao invalido.") from exc
