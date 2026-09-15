"""Repositorio SQLAlchemy async de usuarios (implementa UserRepositoryPort)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.users.adapters.models import UserModel
from modules.users.application.ports import UserRepositoryPort
from modules.users.domain.entities import User


class SQLAlchemyUserRepository(UserRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        stmt = select(UserModel).where(UserModel.google_sub == google_sub)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.lower())
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        if model is None:
            model = UserModel(id=user.id)
            self._session.add(model)
        model.email = user.email.lower()
        model.name = user.name
        model.google_sub = user.google_sub
        model.avatar_url = user.avatar_url
        model.generation_credits = user.generation_credits
        model.updated_at = user.updated_at
        await self._session.flush()
        return user

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            name=model.name,
            google_sub=model.google_sub,
            avatar_url=model.avatar_url,
            generation_credits=model.generation_credits,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
