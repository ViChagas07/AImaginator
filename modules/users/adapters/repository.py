"""Repositorio SQLAlchemy async de usuarios (implementa UserRepositoryPort)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.users.adapters.models import UserModel, UserSettingsModel
from modules.users.application.ports import UserRepositoryPort
from modules.users.domain.entities import User, UserSettings


class SQLAlchemyUserRepository(UserRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    async def get_by_id_for_update(self, user_id: UUID) -> User | None:
        stmt = (
            select(UserModel)
            .where(UserModel.id == user_id)
            .with_for_update()
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        stmt = select(UserModel).where(UserModel.google_sub == google_sub)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.lower())
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_handle(self, handle: str) -> User | None:
        stmt = select(UserModel).where(UserModel.handle == handle)
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
        model.password_hash = user.password_hash
        model.avatar_url = user.avatar_url
        model.avatar_object_key = user.avatar_object_key
        model.bio = user.bio
        model.handle = user.handle
        model.generation_credits = user.generation_credits
        model.plan = user.plan
        model.role = user.role
        model.credits_period_start = user.credits_period_start
        model.moderation_flag = user.moderation_flag
        model.moderation_blocked_until = user.moderation_blocked_until
        model.updated_at = user.updated_at
        await self._session.flush()
        return user

    async def get_settings(self, user_id: UUID) -> UserSettings | None:
        model = await self._session.get(UserSettingsModel, user_id)
        return self._to_settings_entity(model) if model else None

    async def list_flagged(self, *, limit: int = 100) -> list[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.moderation_flag.is_(True))
            .order_by(UserModel.updated_at.desc())
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_period_due(self, *, before, limit: int = 1000) -> list[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.credits_period_start < before)
            .order_by(UserModel.credits_period_start.asc())
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(model) for model in models]

    async def save_settings(self, settings: UserSettings) -> UserSettings:
        model = await self._session.get(UserSettingsModel, settings.user_id)
        if model is None:
            model = UserSettingsModel(user_id=settings.user_id)
            self._session.add(model)
        model.theme = settings.theme
        model.bold_text = settings.bold_text
        model.font_size = settings.font_size
        model.element_spacing = settings.element_spacing
        model.locale = settings.locale
        model.timezone = settings.timezone
        model.high_contrast = settings.high_contrast
        model.screen_reader_optimized = settings.screen_reader_optimized
        model.keyboard_navigation = settings.keyboard_navigation
        model.focus_indicator = settings.focus_indicator
        model.dyslexia_font = settings.dyslexia_font
        model.reduced_motion = settings.reduced_motion
        model.email_notifications = settings.email_notifications
        model.push_notifications = settings.push_notifications
        model.desktop_notifications = settings.desktop_notifications
        model.sound_notifications = settings.sound_notifications
        model.summary_frequency = settings.summary_frequency
        model.notification_email = settings.notification_email
        model.privacy_policy_version = settings.privacy_policy_version
        model.terms_version = settings.terms_version
        model.consented_at = settings.consented_at
        model.developer_mode = settings.developer_mode
        model.updated_at = settings.updated_at
        await self._session.flush()
        return settings

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            name=model.name,
            google_sub=model.google_sub,
            password_hash=model.password_hash,
            avatar_url=model.avatar_url,
            avatar_object_key=model.avatar_object_key,
            bio=model.bio,
            handle=model.handle,
            generation_credits=model.generation_credits,
            plan=model.plan,
            role=model.role,
            credits_period_start=model.credits_period_start,
            moderation_flag=model.moderation_flag,
            moderation_blocked_until=model.moderation_blocked_until,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_settings_entity(model: UserSettingsModel) -> UserSettings:
        return UserSettings(
            user_id=model.user_id,
            theme=model.theme,
            bold_text=model.bold_text,
            font_size=model.font_size,
            element_spacing=model.element_spacing,
            locale=model.locale,
            timezone=model.timezone,
            high_contrast=model.high_contrast,
            screen_reader_optimized=model.screen_reader_optimized,
            keyboard_navigation=model.keyboard_navigation,
            focus_indicator=model.focus_indicator,
            dyslexia_font=model.dyslexia_font,
            reduced_motion=model.reduced_motion,
            email_notifications=model.email_notifications,
            push_notifications=model.push_notifications,
            desktop_notifications=model.desktop_notifications,
            sound_notifications=model.sound_notifications,
            summary_frequency=model.summary_frequency,
            notification_email=model.notification_email,
            privacy_policy_version=model.privacy_policy_version,
            terms_version=model.terms_version,
            consented_at=model.consented_at,
            developer_mode=model.developer_mode,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
