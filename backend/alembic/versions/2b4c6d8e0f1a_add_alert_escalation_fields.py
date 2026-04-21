"""add alert escalation fields

Revision ID: 2b4c6d8e0f1a
Revises: 1a2b3c4d5e6f
Create Date: 2026-03-23 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "2b4c6d8e0f1a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "escalation_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "escalation_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.create_index("ix_alerts_escalation_required", ["escalation_required"], unique=False)
        batch_op.create_index("ix_alerts_escalated_at", ["escalated_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index("ix_alerts_escalated_at")
        batch_op.drop_index("ix_alerts_escalation_required")
        batch_op.drop_column("escalation_count")
        batch_op.drop_column("escalated_at")
        batch_op.drop_column("escalation_required")
