from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.enums import AuditActorTypeEnum, AuditTargetTypeEnum
from app.models.audit_log import AuditLog


def _enum_or_str(value: str | AuditActorTypeEnum | AuditTargetTypeEnum | None) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def record_audit_event(
    db: Session,
    *,
    action_type: str,
    actor_type: str | AuditActorTypeEnum,
    actor_identifier: str | None = None,
    target_type: str | AuditTargetTypeEnum | None = None,
    target_identifier: str | None = None,
    metadata_json: dict | None = None,
) -> AuditLog:
    """Persist an audit log as a required action.

    This function commits the current session. When used after staging domain
    mutations in the same session, commit is atomic for business data + audit.
    """
    event = AuditLog(
        action_type=action_type,
        actor_type=_enum_or_str(actor_type) or "system",
        actor_identifier=actor_identifier,
        target_type=_enum_or_str(target_type),
        target_identifier=target_identifier,
        metadata_json=metadata_json,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def try_record_audit_event(
    db: Session,
    *,
    action_type: str,
    actor_type: str | AuditActorTypeEnum,
    actor_identifier: str | None = None,
    target_type: str | AuditTargetTypeEnum | None = None,
    target_identifier: str | None = None,
    metadata_json: dict | None = None,
) -> None:
    """Best-effort audit helper.

    Never raises on failure and rolls back the session to leave it usable.
    Use only for low-risk, non-blocking audit events.
    """
    try:
        record_audit_event(
            db,
            action_type=action_type,
            actor_type=actor_type,
            actor_identifier=actor_identifier,
            target_type=target_type,
            target_identifier=target_identifier,
            metadata_json=metadata_json,
        )
    except Exception:
        # Auditoría best-effort para no alterar el flujo funcional existente.
        db.rollback()