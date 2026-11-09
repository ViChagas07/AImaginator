"""product features: library, sharing, reports, favorites and CANCELED.

Revision ID: 20261110_120000
Revises: 20261109_120000
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261110_120000"
down_revision: str | None = "20261109_120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "generations",
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_generations_is_favorite", "generations", ["is_favorite"])
    op.create_index("ix_generations_hidden_at", "generations", ["hidden_at"])
    # Status CANCELED e um valor de varchar; nao exige DDL.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_generations_prompt_fts "
        "ON generations USING gin (to_tsvector('simple', prompt))"
    )

    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])
    op.create_index(
        "ix_collections_user_position", "collections", ["user_id", "position"]
    )

    op.create_table(
        "collection_items",
        sa.Column(
            "collection_id",
            sa.Uuid(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "generation_id",
            sa.Uuid(),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_collection_items_generation", "collection_items", ["generation_id"])

    op.create_table(
        "generation_tags",
        sa.Column(
            "generation_id",
            sa.Uuid(),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tag", sa.String(32), primary_key=True),
        sa.Column("normalized", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_generation_tags_normalized", "generation_tags", ["normalized"])

    op.create_table(
        "share_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "generation_id",
            sa.Uuid(),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("allow_prompt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_share_links_generation", "share_links", ["generation_id"])
    op.create_index("ix_share_links_user", "share_links", ["user_id"])
    op.create_index("ix_share_links_token_hash", "share_links", ["token_hash"], unique=True)

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "generation_id",
            sa.Uuid(),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reporter_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("anonymous_session_id", sa.String(128), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("details", sa.String(500), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("action", sa.String(32), nullable=True),
        sa.Column(
            "reviewer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_generation", "reports", ["generation_id"])
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_created", "reports", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_reports_created", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_generation", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_share_links_token_hash", table_name="share_links")
    op.drop_index("ix_share_links_user", table_name="share_links")
    op.drop_index("ix_share_links_generation", table_name="share_links")
    op.drop_table("share_links")
    op.drop_index("ix_generation_tags_normalized", table_name="generation_tags")
    op.drop_table("generation_tags")
    op.drop_index("ix_collection_items_generation", table_name="collection_items")
    op.drop_table("collection_items")
    op.drop_index("ix_collections_user_position", table_name="collections")
    op.drop_index("ix_collections_user_id", table_name="collections")
    op.drop_table("collections")
    op.execute("DROP INDEX IF EXISTS ix_generations_prompt_fts")
    op.drop_index("ix_generations_hidden_at", table_name="generations")
    op.drop_index("ix_generations_is_favorite", table_name="generations")
    op.drop_column("generations", "hidden_at")
    op.drop_column("generations", "is_favorite")
