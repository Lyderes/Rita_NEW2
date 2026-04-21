"""add conversation system

Revision ID: f1a2b3c4d5e6
Revises: e729e354ef9c
Create Date: 2026-04-14 10:00:00.000000

Crea las tres tablas del sistema conversacional:
  - conversation_sessions
  - conversation_messages
  - conversation_memories
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e729e354ef9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # conversation_sessions
    # -----------------------------------------------------------------------
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("session_summary", sa.Text(), nullable=True),
        sa.Column("summary_turn_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("follow_up_suggestion", sa.String(length=500), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_sessions_user_id", "conversation_sessions", ["user_id"]
    )
    op.create_index(
        "ix_conversation_sessions_status", "conversation_sessions", ["status"]
    )
    op.create_index(
        "ix_conversation_sessions_last_activity_at",
        "conversation_sessions",
        ["last_activity_at"],
    )

    # -----------------------------------------------------------------------
    # conversation_messages
    # -----------------------------------------------------------------------
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        # Campos normalizados de análisis (ajuste #2)
        sa.Column("mood", sa.String(length=20), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("requested_help", sa.Boolean(), nullable=True),
        sa.Column("routine_change_detected", sa.Boolean(), nullable=True),
        # JSON completo para auditoría
        sa.Column("raw_analysis_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_session_id", "conversation_messages", ["session_id"]
    )
    op.create_index(
        "ix_conversation_messages_user_id", "conversation_messages", ["user_id"]
    )
    op.create_index(
        "ix_conversation_messages_role", "conversation_messages", ["role"]
    )
    op.create_index(
        "ix_conversation_messages_risk_level", "conversation_messages", ["risk_level"]
    )
    op.create_index(
        "ix_conversation_messages_created_at", "conversation_messages", ["created_at"]
    )

    # -----------------------------------------------------------------------
    # conversation_memories
    # -----------------------------------------------------------------------
    op.create_table(
        "conversation_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memory_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "confidence",
            sa.String(length=20),
            nullable=False,
            server_default="medium",
        ),
        # Trazabilidad fina (ajuste #1)
        sa.Column("source_session_id", sa.Integer(), nullable=True),
        sa.Column("source_message_id", sa.Integer(), nullable=True),
        sa.Column(
            "first_mentioned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        # Política de expiración (ajuste #7)
        sa.Column("expires_after_days", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_session_id"],
            ["conversation_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["conversation_messages.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_memories_user_id", "conversation_memories", ["user_id"]
    )
    op.create_index(
        "ix_conversation_memories_memory_type", "conversation_memories", ["memory_type"]
    )
    op.create_index(
        "ix_conversation_memories_is_active", "conversation_memories", ["is_active"]
    )
    op.create_index(
        "ix_conversation_memories_last_confirmed_at",
        "conversation_memories",
        ["last_confirmed_at"],
    )
    op.create_index(
        "ix_conversation_memories_user_type_active",
        "conversation_memories",
        ["user_id", "memory_type", "is_active"],
    )


def downgrade() -> None:
    op.drop_table("conversation_memories")
    op.drop_table("conversation_messages")
    op.drop_table("conversation_sessions")
