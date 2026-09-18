"""user_settings table + profile fields (bio, handle, timezone, oauth_providers)

Revision ID: 20260918_161435
Revises: 0002_prompt_quota_and_gallery
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_161435"
down_revision: str | None = "0002_prompt_quota_and_gallery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users: adicionar bio e handle.
    op.add_column("users", sa.Column("bio", sa.String(160), nullable=True))
    op.add_column("users", sa.Column("handle", sa.String(50), nullable=True))
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)

    # avatar_url: ampliar para Text (data URL de avatares croppados pode
    # exceder o limite anterior de 2048 caracteres).
    op.alter_column(
        "users", "avatar_url", existing_type=sa.String(2048), type_=sa.Text(), nullable=True
    )

    # user_settings table
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        # Aparência
        sa.Column("theme", sa.String(16), nullable=False, server_default="system"),  # dark | light | system
        sa.Column("bold_text", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("font_size", sa.String(16), nullable=False, server_default="medium"),  # small | medium | large | xl
        sa.Column("element_spacing", sa.String(16), nullable=False, server_default="comfortable"),  # compact | comfortable | spacious
        # Idioma e Região
        sa.Column("locale", sa.String(10), nullable=False, server_default="pt-BR"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Sao_Paulo"),
        # Acessibilidade
        sa.Column("high_contrast", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("screen_reader_optimized", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("keyboard_navigation", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("focus_indicator", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dyslexia_font", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reduced_motion", sa.Boolean(), nullable=False, server_default="false"),
        # Notificações
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("push_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("desktop_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sound_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("summary_frequency", sa.String(16), nullable=False, server_default="weekly"),  # daily | weekly | never
        sa.Column("notification_email", sa.String(320), nullable=True),
        # Privacidade
        sa.Column("privacy_policy_version", sa.String(32), nullable=True),
        sa.Column("terms_version", sa.String(32), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        # Avançado
        sa.Column("developer_mode", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_index("ix_users_handle", table_name="users")
    op.drop_column("users", "handle")
    op.drop_column("users", "bio")
    op.alter_column(
        "users", "avatar_url", existing_type=sa.Text(), type_=sa.String(2048), nullable=True
    )