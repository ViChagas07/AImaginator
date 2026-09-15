"""Repositorio SQLAlchemy de geracoes (anti N+1: eager loading explicito).

Toda query que atravessar relacionamentos DEVE usar selectinload/
joinedload (spec secao 9.2). Lazy loading implicito e proibido: em
contexto async ele explode em MissingGreenlet.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.image_generation.adapters.repositories.models import GenerationModel
from modules.image_generation.application.ports import GenerationRepositoryPort
from modules.image_generation.domain.entities import (
    AspectRatio,
    Generation,
    GenerationKind,
    GenerationStatus,
    StylePreset,
)


class SQLAlchemyGenerationRepository(GenerationRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, generation_id: UUID) -> Generation | None:
        model = await self._session.get(GenerationModel, generation_id)
        return self._to_entity(model) if model else None

    async def save(self, generation: Generation) -> Generation:
        model = await self._session.get(GenerationModel, generation.id)
        if model is None:
            model = GenerationModel(id=generation.id, user_id=generation.user_id)
            self._session.add(model)
        model.kind = generation.kind.value
        model.status = generation.status.value
        model.prompt = generation.prompt
        model.negative_prompt = generation.negative_prompt
        model.style_preset = generation.style_preset.value
        model.aspect_ratio = generation.aspect_ratio.value
        model.source_image_url = generation.source_image_url
        model.result_image_url = generation.result_image_url
        model.error_message = generation.error_message
        model.credits_cost = generation.credits_cost
        model.updated_at = generation.updated_at
        model.completed_at = generation.completed_at
        await self._session.flush()
        return generation

    async def list_by_user(
        self, user_id: UUID, *, cursor: UUID | None, limit: int
    ) -> list[Generation]:
        stmt = (
            select(GenerationModel)
            .where(GenerationModel.user_id == user_id)
            .order_by(GenerationModel.created_at.desc(), GenerationModel.id.desc())
            .limit(limit)
        )
        if cursor is not None:
            cursor_model = await self._session.get(GenerationModel, cursor)
            if cursor_model is not None:
                stmt = stmt.where(
                    (GenerationModel.created_at < cursor_model.created_at)
                    | (
                        (GenerationModel.created_at == cursor_model.created_at)
                        & (GenerationModel.id < cursor_model.id)
                    )
                )
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_public_showcase(self, *, limit: int) -> list[Generation]:
        stmt = (
            select(GenerationModel)
            .where(GenerationModel.status == GenerationStatus.DONE.value)
            .where(GenerationModel.result_image_url.isnot(None))
            .order_by(GenerationModel.created_at.desc())
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in models]

    @staticmethod
    def _to_entity(model: GenerationModel) -> Generation:
        return Generation(
            id=model.id,
            user_id=model.user_id,
            kind=GenerationKind(model.kind),
            status=GenerationStatus(model.status),
            prompt=model.prompt,
            negative_prompt=model.negative_prompt,
            style_preset=StylePreset(model.style_preset or StylePreset.NONE.value),
            aspect_ratio=AspectRatio(model.aspect_ratio or AspectRatio.SQUARE.value),
            source_image_url=model.source_image_url,
            result_image_url=model.result_image_url,
            error_message=model.error_message,
            credits_cost=model.credits_cost,
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )
