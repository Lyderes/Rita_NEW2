"""add frontend users table

Revision ID: 1a2b3c4d5e6f
Revises: f3a7c1d9e2b4
Create Date: 2026-03-17 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "frontend_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_frontend_users_username",
        "frontend_users",
        ["username"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_frontend_users_username", table_name="frontend_users")
    op.drop_table("frontend_users")
