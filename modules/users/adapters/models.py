"""Modelos ORM do modulo users (camada adapters — nunca expostos na API)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    handle: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    generation_credits: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class UserSettingsModel(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Aparência
    # dark | light | system
    theme: Mapped[str] = mapped_column(String(16), default="system")
    bold_text: Mapped[bool] = mapped_column(Boolean, default=False)
    # small | medium | large | xl
    font_size: Mapped[str] = mapped_column(String(16), default="medium")
    # compact | comfortable | spacious
    element_spacing: Mapped[str] = mapped_column(String(16), default="comfortable")
    # Idioma e Região
    locale: Mapped[str] = mapped_column(String(10), default="pt-BR")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    # Acessibilidade
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False)
    screen_reader_optimized: Mapped[bool] = mapped_column(Boolean, default=False)
    keyboard_navigation: Mapped[bool] = mapped_column(Boolean, default=False)
    focus_indicator: Mapped[bool] = mapped_column(Boolean, default=False)
    dyslexia_font: Mapped[bool] = mapped_column(Boolean, default=False)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    # Notificações
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    push_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    desktop_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    sound_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    # daily | weekly | never
    summary_frequency: Mapped[str] = mapped_column(String(16), default="weekly")
    notification_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Privacidade
    privacy_policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Avançado
    developer_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
