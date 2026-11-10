"""Modelo ORM de generations (adapters — nunca exposto na API)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class GenerationModel(Base):
    __tablename__ = "generations"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('generate','edit','upscale')",
            name="ck_generations_kind",
        ),
        CheckConstraint(
            "status IN ('queued','processing','done','failed','canceled')",
            name="ck_generations_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    anonymous_session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_preset: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    original_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parent_generation_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("generations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warning_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    locale: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quota_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    credits_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    upscale_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    credits_cost: Mapped[int] = mapped_column(Integer, default=1)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    hidden_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class ModerationEventModel(Base):
    __tablename__ = "moderation_events"
    __table_args__ = (
        Index("ix_moderation_events_user_created", "user_id", "created_at"),
        Index(
            "ix_moderation_events_anon_created", "anonymous_session_id", "created_at"
        ),
        Index("ix_moderation_events_ip_created", "ip_hash", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    anonymous_session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_length: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class CollectionModel(Base):
    __tablename__ = "collections"
    __table_args__ = (Index("ix_collections_user_position", "user_id", "position"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class CollectionItemModel(Base):
    __tablename__ = "collection_items"

    collection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    generation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("generations.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class GenerationTagModel(Base):
    __tablename__ = "generation_tags"

    generation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("generations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag: Mapped[str] = mapped_column(String(32), primary_key=True)
    normalized: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ShareLinkModel(Base):
    __tablename__ = "share_links"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    generation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    allow_prompt: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ReportModel(Base):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_status_created", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    generation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    reporter_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    anonymous_session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    details: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
