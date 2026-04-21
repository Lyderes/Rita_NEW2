"""add trace_id to events

Revision ID: d9e1f3a4b5c6
Revises: c7a9f2b1d4e8
Create Date: 2026-03-13 20:00:00.000000

"""
from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d9e1f3a4b5c6"
down_revision = "c7a9f2b1d4e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trace_id", sa.String(length=36), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM events")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE events SET trace_id = :trace_id WHERE id = :id"),
            {"trace_id": str(uuid4()), "id": row.id},
        )

    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.alter_column("trace_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_index("ix_events_trace_id", ["trace_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index("ix_events_trace_id")
        batch_op.drop_column("trace_id")
