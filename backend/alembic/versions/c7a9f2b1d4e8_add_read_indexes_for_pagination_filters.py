"""add read indexes for pagination and filters

Revision ID: c7a9f2b1d4e8
Revises: b6f4d1c2e3a7
Create Date: 2026-03-13 16:00:00.000000

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "c7a9f2b1d4e8"
down_revision = "b6f4d1c2e3a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index("ix_events_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_events_device_id", ["device_id"], unique=False)
        batch_op.create_index("ix_events_created_at", ["created_at"], unique=False)
        batch_op.create_index("ix_events_severity", ["severity"], unique=False)
        batch_op.create_index("ix_events_event_type", ["event_type"], unique=False)

    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.create_index("ix_incidents_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_incidents_device_id", ["device_id"], unique=False)
        batch_op.create_index("ix_incidents_status", ["status"], unique=False)
        batch_op.create_index("ix_incidents_opened_at", ["opened_at"], unique=False)
        batch_op.create_index("ix_incidents_severity", ["severity"], unique=False)

    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.create_index("ix_alerts_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_alerts_status", ["status"], unique=False)
        batch_op.create_index("ix_alerts_created_at", ["created_at"], unique=False)
        batch_op.create_index("ix_alerts_severity", ["severity"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index("ix_alerts_severity")
        batch_op.drop_index("ix_alerts_created_at")
        batch_op.drop_index("ix_alerts_status")
        batch_op.drop_index("ix_alerts_user_id")

    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.drop_index("ix_incidents_severity")
        batch_op.drop_index("ix_incidents_opened_at")
        batch_op.drop_index("ix_incidents_status")
        batch_op.drop_index("ix_incidents_device_id")
        batch_op.drop_index("ix_incidents_user_id")

    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index("ix_events_event_type")
        batch_op.drop_index("ix_events_severity")
        batch_op.drop_index("ix_events_created_at")
        batch_op.drop_index("ix_events_device_id")
        batch_op.drop_index("ix_events_user_id")
