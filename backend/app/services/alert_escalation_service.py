import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import AlertStatusEnum, NotificationChannelEnum, NotificationJobStatusEnum, SeverityEnum
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.frontend_user import FrontendUser
from app.models.notification_job import NotificationJob

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AlertEscalationResult:
    scanned_pending_alerts: int
    overdue_pending_alerts: int
    escalated_alerts: int
    already_escalated_alerts: int
    skipped_recent_pending_alerts: int
    notification_jobs_created: int


@dataclass(frozen=True, slots=True)
class NotificationCreationPolicy:
    channel: NotificationChannelEnum
    max_retries: int
    base_backoff_seconds: int


DEFAULT_NOTIFICATION_POLICY = NotificationCreationPolicy(
    channel=NotificationChannelEnum.mock,
    max_retries=2,
    base_backoff_seconds=45,
)

NOTIFICATION_POLICY_BY_SEVERITY: dict[SeverityEnum, NotificationCreationPolicy] = {
    SeverityEnum.critical: NotificationCreationPolicy(
        channel=NotificationChannelEnum.sms,
        max_retries=5,
        base_backoff_seconds=10,
    ),
    SeverityEnum.high: NotificationCreationPolicy(
        channel=NotificationChannelEnum.push,
        max_retries=4,
        base_backoff_seconds=15,
    ),
    SeverityEnum.medium: NotificationCreationPolicy(
        channel=NotificationChannelEnum.push,
        max_retries=2,
        base_backoff_seconds=45,
    ),
    SeverityEnum.low: NotificationCreationPolicy(
        channel=NotificationChannelEnum.mock,
        max_retries=1,
        base_backoff_seconds=90,
    ),
}


def _get_notification_policy_for_alert(alert: Alert) -> NotificationCreationPolicy:
    return NOTIFICATION_POLICY_BY_SEVERITY.get(alert.severity, DEFAULT_NOTIFICATION_POLICY)


def _get_caregiver_tokens(db: Session) -> list[str]:
    """Returns FCM tokens for all caregivers who have registered one."""
    rows = db.scalars(
        select(FrontendUser.fcm_token).where(FrontendUser.fcm_token.is_not(None))
    ).all()
    return [t for t in rows if t]


def _ensure_notification_job_for_alert(
    db: Session,
    *,
    alert: Alert,
    source: str,
) -> bool:
    policy = _get_notification_policy_for_alert(alert)

    # Downgrade push → mock when no caregiver has registered an FCM token
    effective_channel = policy.channel
    if policy.channel == NotificationChannelEnum.push:
        tokens = _get_caregiver_tokens(db)
        if not tokens:
            effective_channel = NotificationChannelEnum.mock
        else:
            # Store all tokens; worker uses the first available one
            pass

    existing = db.scalar(
        select(NotificationJob).where(
            NotificationJob.alert_id == alert.id,
            NotificationJob.channel == effective_channel,
        )
    )
    if existing is not None:
        return False

    payload_json: dict = {
        "source": source,
        "alert_id": alert.id,
        "incident_id": alert.incident_id,
        "user_id": alert.user_id,
        "alert_type": alert.alert_type.value,
        "severity": alert.severity.value,
        "message": alert.message,
        "channel": effective_channel.value,
        "max_retries": policy.max_retries,
        "base_backoff_seconds": policy.base_backoff_seconds,
        "escalated_at": _normalize_timestamp(alert.escalated_at).isoformat()
        if alert.escalated_at is not None
        else None,
    }

    if effective_channel == NotificationChannelEnum.push:
        tokens = _get_caregiver_tokens(db)
        payload_json["fcm_token"] = tokens[0]  # primary caregiver
        payload_json["fcm_tokens_all"] = tokens  # for future fan-out

    db.add(
        NotificationJob(
            alert_id=alert.id,
            channel=effective_channel,
            status=NotificationJobStatusEnum.pending,
            payload_json=payload_json,
            max_retries=policy.max_retries,
            base_backoff_seconds=policy.base_backoff_seconds,
        )
    )
    return True


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def run_alert_escalation_once(
    db: Session,
    *,
    now: datetime | None = None,
    pending_threshold_minutes: int = 10,
    source: str = "alert-escalation-monitor",
) -> AlertEscalationResult:
    current_time = _normalize_timestamp(now) or datetime.now(UTC)
    pending_cutoff = current_time - timedelta(minutes=max(pending_threshold_minutes, 1))
    # Using list comprehension for status matching to avoid Enum identity issues in tests/SQLite
    # This is more robust when the same Enum class is imported from different paths in a test environment
    all_alerts = list(db.scalars(select(Alert)).all())
    pending_alerts = [
        a for a in all_alerts 
        if a.status == AlertStatusEnum.pending or str(a.status) == "pending" or str(a.status) == "AlertStatusEnum.pending"
    ]
    overdue_pending_alerts = 0
    escalated_alerts = 0
    already_escalated_alerts = 0
    skipped_recent_pending_alerts = 0
    notification_jobs_created = 0

    for alert in pending_alerts:
        created_at = _normalize_timestamp(alert.created_at) or current_time
        if created_at > pending_cutoff:
            skipped_recent_pending_alerts += 1
            continue

        overdue_pending_alerts += 1
        if alert.escalation_required:
            already_escalated_alerts += 1
            continue

        alert.escalation_required = True
        alert.escalated_at = current_time
        alert.escalation_count = (alert.escalation_count or 0) + 1
        db.add(alert)

        db.add(
            AuditLog(
                action_type="alert.escalate",
                actor_type="system",
                actor_identifier=source,
                target_type="alert",
                target_identifier=str(alert.id),
                metadata_json={
                    "source": source,
                    "reason": "pending_timeout",
                    "pending_threshold_minutes": pending_threshold_minutes,
                    "incident_id": alert.incident_id,
                    "alert_type": alert.alert_type.value,
                    "severity": alert.severity.value,
                    "escalation_count": alert.escalation_count,
                },
            )
        )
        if _ensure_notification_job_for_alert(db, alert=alert, source=source):
            notification_jobs_created += 1
        escalated_alerts += 1

    if escalated_alerts > 0:
        db.commit()

    return AlertEscalationResult(
        scanned_pending_alerts=len(pending_alerts),
        overdue_pending_alerts=overdue_pending_alerts,
        escalated_alerts=escalated_alerts,
        already_escalated_alerts=already_escalated_alerts,
        skipped_recent_pending_alerts=skipped_recent_pending_alerts,
        notification_jobs_created=notification_jobs_created,
    )
