"""prompt quota + gallery: nullable google_sub, password, anonymous arts

Revision ID: 0002_prompt_quota_and_gallery
Revises: 0001_initial
Create Date: 2026-09-18 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_prompt_quota_and_gallery"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users: contas com email/senha (google_sub deixa de ser obrigatorio).
    op.alter_column("users", "google_sub", existing_type=sa.String(255), nullable=True)
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))

    # generations: artes anonimas temporarias + titulo + soft delete.
    op.alter_column("generations", "user_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("generations", sa.Column("anonymous_session_id", sa.String(128), nullable=True))
    op.add_column("generations", sa.Column("title", sa.String(200), nullable=True))
    op.add_column(
        "generations", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_generations_anonymous_session_id", "generations", ["anonymous_session_id"]
    )
    op.create_index("ix_generations_deleted_at", "generations", ["deleted_at"])
    op.create_index("ix_generations_user_id", "generations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_generations_user_id", table_name="generations")
    op.drop_index("ix_generations_deleted_at", table_name="generations")
    op.drop_index("ix_generations_anonymous_session_id", table_name="generations")
    op.drop_column("generations", "deleted_at")
    op.drop_column("generations", "title")
    op.drop_column("generations", "anonymous_session_id")
    op.alter_column("generations", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("users", "password_hash")
    op.alter_column("users", "google_sub", existing_type=sa.String(255), nullable=False)
