"""platform hardening: plans, credit ledger, admin audit and avatar key

Revision ID: 20261109_120000
Revises: 20261106_150000
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261109_120000"
down_revision: str | None = "20261106_150000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("plan", sa.String(16), nullable=False, server_default="free"),
    )
    op.add_column(
        "users",
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column(
            "credits_period_start",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("avatar_object_key", sa.String(512), nullable=True),
    )
    # Remove data URLs antigas do banco; o blob passa a viver no S3.
    op.execute("UPDATE users SET avatar_url = NULL WHERE avatar_url LIKE 'data:%'")

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])
    op.create_index(
        "ix_credit_ledger_created_at", "credit_ledger", ["created_at"]
    )

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(128), nullable=True),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_admin_audit_log_created_at", "admin_audit_log", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_log_created_at", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_index("ix_credit_ledger_created_at", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_user_id", table_name="credit_ledger")
    op.drop_table("credit_ledger")
    op.drop_column("users", "avatar_object_key")
    op.drop_column("users", "credits_period_start")
    op.drop_column("users", "role")
    op.drop_column("users", "plan")
