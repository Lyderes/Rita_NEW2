"""add notification jobs table

Revision ID: 4d6e8f0a1b2c
Revises: 2b4c6d8e0f1a
Create Date: 2026-03-23 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "4d6e8f0a1b2c"
down_revision = "2b4c6d8e0f1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False, server_default="mock"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", "channel", name="uq_notification_jobs_alert_channel"),
    )
    op.create_index("ix_notification_jobs_status", "notification_jobs", ["status"], unique=False)
    op.create_index("ix_notification_jobs_channel", "notification_jobs", ["channel"], unique=False)
    op.create_index("ix_notification_jobs_created_at", "notification_jobs", ["created_at"], unique=False)
    op.create_index("ix_notification_jobs_processed_at", "notification_jobs", ["processed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_jobs_processed_at", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_created_at", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_channel", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_status", table_name="notification_jobs")
    op.drop_table("notification_jobs")
