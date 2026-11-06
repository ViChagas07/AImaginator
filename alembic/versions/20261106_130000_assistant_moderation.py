"""assistant moderation: generation locale/ip/refund, user flags, events

Revision ID: 20261106_130000
Revises: 20261106_120000
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261106_130000"
down_revision: str | None = "20261106_120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("locale", sa.String(16), nullable=True))
    op.add_column("generations", sa.Column("ip_hash", sa.String(64), nullable=True))
    op.add_column(
        "generations", sa.Column("warning_level", sa.Integer(), nullable=True)
    )
    op.add_column(
        "generations", sa.Column("warning_message", sa.Text(), nullable=True)
    )
    op.add_column(
        "generations",
        sa.Column(
            "quota_refunded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "moderation_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "moderation_blocked_until", sa.DateTime(timezone=True), nullable=True
        ),
    )

    op.create_table(
        "moderation_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("anonymous_session_id", sa.String(128), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("layer", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("prompt_length", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_moderation_events_user_id", "moderation_events", ["user_id"])
    op.create_index(
        "ix_moderation_events_anonymous_session_id",
        "moderation_events",
        ["anonymous_session_id"],
    )
    op.create_index("ix_moderation_events_ip_hash", "moderation_events", ["ip_hash"])
    op.create_index(
        "ix_moderation_events_category", "moderation_events", ["category"]
    )
    op.create_index(
        "ix_moderation_events_created_at", "moderation_events", ["created_at"]
    )
    op.create_index(
        "ix_moderation_events_user_created",
        "moderation_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_moderation_events_anon_created",
        "moderation_events",
        ["anonymous_session_id", "created_at"],
    )
    op.create_index(
        "ix_moderation_events_ip_created",
        "moderation_events",
        ["ip_hash", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("moderation_events")
    op.drop_column("users", "moderation_blocked_until")
    op.drop_column("users", "moderation_flag")
    op.drop_column("generations", "quota_refunded")
    op.drop_column("generations", "warning_message")
    op.drop_column("generations", "warning_level")
    op.drop_column("generations", "ip_hash")
    op.drop_column("generations", "locale")
