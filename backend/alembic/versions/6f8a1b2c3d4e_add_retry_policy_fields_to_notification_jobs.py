"""add retry policy fields to notification jobs

Revision ID: 6f8a1b2c3d4e
Revises: 4d6e8f0a1b2c
Create Date: 2026-03-23 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "6f8a1b2c3d4e"
down_revision = "4d6e8f0a1b2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notification_jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("max_retries", sa.Integer(), nullable=False, server_default=sa.text("3")))
        batch_op.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_notification_jobs_next_attempt_at", ["next_attempt_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("notification_jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_notification_jobs_next_attempt_at")
        batch_op.drop_column("next_attempt_at")
        batch_op.drop_column("max_retries")
