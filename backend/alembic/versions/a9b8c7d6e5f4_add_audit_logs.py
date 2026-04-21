"""add audit logs table

Revision ID: a9b8c7d6e5f4
Revises: f3a7c1d9e2b4
Create Date: 2026-03-16 13:30:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "f3a7c1d9e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_identifier", sa.String(length=255), nullable=True),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_identifier", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
