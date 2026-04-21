"""add device administrative lifecycle

Revision ID: f3a7c1d9e2b4
Revises: e1f2a3b4c5d6
Create Date: 2026-03-16 12:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f3a7c1d9e2b4"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


device_admin_status_enum = sa.Enum(
    "active",
    "suspended",
    "revoked",
    "retired",
    name="device_admin_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "admin_status",
                device_admin_status_enum,
                nullable=False,
                server_default="active",
            )
        )
        batch_op.add_column(sa.Column("admin_status_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("token_rotated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "provisioned_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            )
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE devices
            SET admin_status = 'active'
            WHERE admin_status IS NULL
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE devices
            SET provisioned_at = CURRENT_TIMESTAMP
            WHERE provisioned_at IS NULL
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("provisioned_at")
        batch_op.drop_column("token_rotated_at")
        batch_op.drop_column("admin_status_reason")
        batch_op.drop_column("admin_status")
