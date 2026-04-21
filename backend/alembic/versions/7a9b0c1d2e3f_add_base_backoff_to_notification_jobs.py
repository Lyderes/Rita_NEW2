"""add base backoff to notification jobs

Revision ID: 7a9b0c1d2e3f
Revises: 6f8a1b2c3d4e
Create Date: 2026-03-23 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7a9b0c1d2e3f"
down_revision = "6f8a1b2c3d4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notification_jobs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "base_backoff_seconds",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("30"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("notification_jobs", schema=None) as batch_op:
        batch_op.drop_column("base_backoff_seconds")
