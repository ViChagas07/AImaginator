"""studio: parent_generation_id and credits_refunded

Revision ID: 20261106_140000
Revises: 20261106_130000
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261106_140000"
down_revision: str | None = "20261106_130000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("parent_generation_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_generations_parent_generation_id",
        "generations",
        "generations",
        ["parent_generation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_generations_parent_generation_id",
        "generations",
        ["parent_generation_id"],
    )
    op.add_column(
        "generations",
        sa.Column(
            "credits_refunded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("generations", "credits_refunded")
    op.drop_index("ix_generations_parent_generation_id", table_name="generations")
    op.drop_constraint(
        "fk_generations_parent_generation_id", "generations", type_="foreignkey"
    )
    op.drop_column("generations", "parent_generation_id")
