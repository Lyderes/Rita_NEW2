import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.conversation_memory import ConversationMemory
from app.models.conversation_message import ConversationMessage
from app.models.conversation_session import ConversationSession
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User

logger = logging.getLogger(__name__)


class UserNotFoundError(Exception):
    pass


def _count(db: Session, model, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.user_id == user_id)) or 0


def execute_right_to_be_forgotten(db: Session, user_id: int) -> dict[str, Any]:
    """
    Executes a physical cascaded deletion of a User and all related data.
    Writes an immutable AuditLog entry before deletion so the action is
    traceable even after the user record is gone.
    """
    user = db.get(User, user_id)
    if not user:
        raise UserNotFoundError(f"User {user_id} not found.")

    # Collect counts before deletion for the audit trail
    deleted_counts = {
        "devices": _count(db, Device, user_id),
        "events": _count(db, Event, user_id),
        "incidents": _count(db, Incident, user_id),
        "alerts": _count(db, Alert, user_id),
        "conversation_sessions": _count(db, ConversationSession, user_id),
        "conversation_messages": _count(db, ConversationMessage, user_id),
        "conversation_memories": _count(db, ConversationMemory, user_id),
    }

    summary = {
        "user_id": user_id,
        "user_name": user.full_name,
        "action": "gdpr_right_to_be_forgotten",
        "deleted_at": datetime.now(UTC).isoformat(),
        "deleted_counts": deleted_counts,
    }

    try:
        # Write audit entry before deletion (same transaction — AuditLog has no FK to User)
        audit_entry = AuditLog(
            action_type="gdpr_right_to_be_forgotten",
            actor_type="frontend_user",
            target_type="user",
            target_identifier=str(user_id),
            metadata_json=summary,
        )
        db.add(audit_entry)

        db.delete(user)
        db.commit()

        logger.info(
            "GDPR right_to_be_forgotten executed for user_id=%s (%s)",
            user_id,
            user.full_name,
            extra={"deleted_counts": deleted_counts},
        )
        return summary
    except Exception as e:
        db.rollback()
        logger.error("GDPR deletion failed for User %s: %s", user_id, e)
        raise
