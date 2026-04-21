"""enforce unique trace_id on events

Revision ID: e1f2a3b4c5d6
Revises: d9e1f3a4b5c6
Create Date: 2026-03-13 21:00:00.000000

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d9e1f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index("ix_events_trace_id")
        batch_op.create_unique_constraint("uq_events_trace_id", ["trace_id"])


def downgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_constraint("uq_events_trace_id", type_="unique")
        batch_op.create_index("ix_events_trace_id", ["trace_id"], unique=False)
