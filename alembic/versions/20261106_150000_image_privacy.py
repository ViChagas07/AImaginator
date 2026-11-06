"""image privacy: original_object_key and upscale_refunded

Revision ID: 20261106_150000
Revises: 20261106_140000
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261106_150000"
down_revision: str | None = "20261106_140000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("original_object_key", sa.String(512), nullable=True),
    )
    op.add_column(
        "generations",
        sa.Column(
            "upscale_refunded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("generations", "upscale_refunded")
    op.drop_column("generations", "original_object_key")
