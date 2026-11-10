"""generation status/kind constraints: canceled and upscale.

Revision ID: 20261110_140000
Revises: 20261110_130000_seed_bigint
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261110_140000"
down_revision: str | None = "20261110_130000_seed_bigint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_OLD = "status IN ('queued','processing','done','failed')"
_STATUS_NEW = "status IN ('queued','processing','done','failed','canceled')"
_KIND_OLD = "kind IN ('generate','edit')"
_KIND_NEW = "kind IN ('generate','edit','upscale')"


def upgrade() -> None:
    op.execute("ALTER TABLE generations DROP CONSTRAINT IF EXISTS ck_generations_status")
    op.create_check_constraint("ck_generations_status", "generations", _STATUS_NEW)

    op.execute("ALTER TABLE generations DROP CONSTRAINT IF EXISTS ck_generations_kind")
    op.create_check_constraint("ck_generations_kind", "generations", _KIND_NEW)


def downgrade() -> None:
    conn = op.get_bind()
    canceled = conn.execute(
        sa.text("SELECT count(*) FROM generations WHERE status = 'canceled'")
    ).scalar_one()
    upscale = conn.execute(
        sa.text("SELECT count(*) FROM generations WHERE kind = 'upscale'")
    ).scalar_one()
    if canceled or upscale:
        raise RuntimeError(
            "Downgrade bloqueado: existem linhas com status='canceled' "
            f"({canceled}) ou kind='upscale' ({upscale}). "
            "Migre esses dados antes de reverter."
        )

    op.execute("ALTER TABLE generations DROP CONSTRAINT IF EXISTS ck_generations_status")
    op.create_check_constraint("ck_generations_status", "generations", _STATUS_OLD)

    op.execute("ALTER TABLE generations DROP CONSTRAINT IF EXISTS ck_generations_kind")
    op.create_check_constraint("ck_generations_kind", "generations", _KIND_OLD)
