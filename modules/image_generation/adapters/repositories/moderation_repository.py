"""Repositorio SQLAlchemy de eventos de moderacao."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.image_generation.adapters.repositories.models import ModerationEventModel
from modules.image_generation.application.ports.moderation import (
    ModerationEventRepositoryPort,
)
from modules.image_generation.domain.moderation import ModerationEvent


class SQLAlchemyModerationEventRepository(ModerationEventRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: ModerationEvent) -> None:
        prompt_text = event.prompt_text[:200] if event.prompt_text else None
        self._session.add(
            ModerationEventModel(
                user_id=event.user_id,
                anonymous_session_id=event.anonymous_session_id,
                ip_hash=event.ip_hash,
                locale=event.locale,
                category=event.category.value,
                layer=event.layer.value,
                confidence=event.confidence,
                prompt_hash=event.prompt_hash,
                prompt_length=event.prompt_length,
                prompt_text=prompt_text,
                created_at=event.created_at,
            )
        )
        await self._session.flush()

    async def count_since(
        self,
        *,
        since: datetime,
        user_id: UUID | None = None,
        anonymous_session_id: str | None = None,
        ip_hash: str | None = None,
    ) -> int:
        conditions = [ModerationEventModel.created_at >= since]
        if user_id is not None:
            conditions.append(ModerationEventModel.user_id == user_id)
        else:
            identity = []
            if anonymous_session_id:
                identity.append(
                    ModerationEventModel.anonymous_session_id == anonymous_session_id
                )
            if ip_hash:
                identity.append(ModerationEventModel.ip_hash == ip_hash)
            if not identity:
                return 0
            conditions.append(or_(*identity))
        stmt = select(func.count(ModerationEventModel.id)).where(*conditions)
        return int((await self._session.execute(stmt)).scalar_one())

    async def aggregate_since(self, *, since: datetime) -> list[dict]:
        day = func.date(ModerationEventModel.created_at)
        stmt = (
            select(
                day.label("day"),
                ModerationEventModel.category,
                ModerationEventModel.layer,
                func.count(ModerationEventModel.id).label("count"),
            )
            .where(ModerationEventModel.created_at >= since)
            .group_by(day, ModerationEventModel.category, ModerationEventModel.layer)
            .order_by(day.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "day": str(row.day),
                "category": row.category,
                "layer": row.layer,
                "count": int(row.count),
            }
            for row in rows
        ]
