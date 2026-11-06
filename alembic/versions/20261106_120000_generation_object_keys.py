"""generations: object storage keys, seed and stable error code

Revision ID: 20261106_120000
Revises: 20260918_161435
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261106_120000"
down_revision: str | None = "20260918_161435"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generations", sa.Column("source_object_key", sa.String(512), nullable=True)
    )
    op.add_column(
        "generations", sa.Column("result_object_key", sa.String(512), nullable=True)
    )
    op.add_column("generations", sa.Column("seed", sa.Integer(), nullable=True))
    op.add_column(
        "generations", sa.Column("error_code", sa.String(64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("generations", "error_code")
    op.drop_column("generations", "seed")
    op.drop_column("generations", "result_object_key")
    op.drop_column("generations", "source_object_key")
