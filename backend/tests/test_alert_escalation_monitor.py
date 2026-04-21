from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, NotificationChannelEnum, SeverityEnum
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.incident import Incident
from app.models.notification_job import NotificationJob
from app.models.user import User
from app.services.alert_escalation_service import run_alert_escalation_once


def _make_db() -> Session:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def _seed_pending_alert(
    db: Session,
    *,
    created_at: datetime,
    severity: SeverityEnum = SeverityEnum.high,
    escalation_required: bool = False,
    escalation_count: int = 0,
) -> Alert:
    user = User(full_name="Escalation User", notes="alerts")
    db.add(user)
    db.flush()

    device = Device(
        user_id=user.id,
        device_code=f"esc-device-{user.id}",
        device_name="Esc Device",
        location_name="Lab",
        is_active=True,
    )
    db.add(device)
    db.flush()

    incident = Incident(
        user_id=user.id,
        device_id=device.id,
        incident_type=EventTypeEnum.assistance_needed,
        status=IncidentStatusEnum.open,
        severity=severity,
        summary="Escalation test incident",
    )
    db.add(incident)
    db.flush()

    alert = Alert(
        user_id=user.id,
        incident_id=incident.id,
        alert_type=EventTypeEnum.assistance_needed,
        severity=severity,
        status=AlertStatusEnum.pending,
        message="Alert pending for escalation test",
        created_at=created_at,
        escalation_required=escalation_required,
        escalation_count=escalation_count,
    )
    db.add(alert)
    db.commit()
    return alert


def test_alert_escalation_marks_overdue_pending_alert_and_writes_audit() -> None:
    db = _make_db()
    now = datetime.now(UTC)
    try:
        old_pending = _seed_pending_alert(db, created_at=now - timedelta(minutes=30))
        _seed_pending_alert(db, created_at=now - timedelta(minutes=5))
        _seed_pending_alert(
            db,
            created_at=now - timedelta(minutes=40),
            escalation_required=True,
            escalation_count=1,
        )

        result = run_alert_escalation_once(db, now=now, pending_threshold_minutes=10, source="test-escalation")

        assert result.scanned_pending_alerts == 3
        assert result.overdue_pending_alerts == 2
        assert result.escalated_alerts == 1
        assert result.already_escalated_alerts == 1
        assert result.skipped_recent_pending_alerts == 1
        assert result.notification_jobs_created == 1

        escalated_alert = db.get(Alert, old_pending.id)
        assert escalated_alert is not None
        assert escalated_alert.escalation_required is True
        assert escalated_alert.escalated_at is not None
        assert escalated_alert.escalation_count == 1

        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "alert.escalate", AuditLog.target_identifier == str(old_pending.id))
        )
        assert audit_count == 1

        job_count = db.scalar(
            select(func.count())
            .select_from(NotificationJob)
            .where(NotificationJob.alert_id == old_pending.id)
        )
        assert job_count == 1
    finally:
        db.close()


def test_alert_escalation_is_idempotent_for_already_escalated_pending_alert() -> None:
    db = _make_db()
    now = datetime.now(UTC)
    try:
        pending = _seed_pending_alert(db, created_at=now - timedelta(minutes=25))

        first = run_alert_escalation_once(db, now=now, pending_threshold_minutes=10, source="test-escalation")
        second = run_alert_escalation_once(
            db,
            now=now + timedelta(minutes=1),
            pending_threshold_minutes=10,
            source="test-escalation",
        )

        assert first.escalated_alerts == 1
        assert second.escalated_alerts == 0
        assert second.already_escalated_alerts == 1
        assert first.notification_jobs_created == 1
        assert second.notification_jobs_created == 0

        alert = db.get(Alert, pending.id)
        assert alert is not None
        assert alert.escalation_required is True
        assert alert.escalation_count == 1

        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action_type == "alert.escalate", AuditLog.target_identifier == str(pending.id))
        )
        assert audit_count == 1

        job_count = db.scalar(
            select(func.count())
            .select_from(NotificationJob)
            .where(NotificationJob.alert_id == pending.id)
        )
        assert job_count == 1
    finally:
        db.close()


def test_alert_escalation_applies_notification_policy_by_severity() -> None:
    db = _make_db()
    now = datetime.now(UTC)
    try:
        critical_alert = _seed_pending_alert(
            db,
            created_at=now - timedelta(minutes=30),
            severity=SeverityEnum.critical,
        )
        low_alert = _seed_pending_alert(
            db,
            created_at=now - timedelta(minutes=30),
            severity=SeverityEnum.low,
        )

        result = run_alert_escalation_once(db, now=now, pending_threshold_minutes=10, source="test-escalation")
        assert result.notification_jobs_created == 2

        critical_job = db.scalar(
            select(NotificationJob).where(NotificationJob.alert_id == critical_alert.id)
        )
        low_job = db.scalar(
            select(NotificationJob).where(NotificationJob.alert_id == low_alert.id)
        )

        assert critical_job is not None
        assert low_job is not None

        assert critical_job.channel == NotificationChannelEnum.sms
        assert critical_job.max_retries == 5
        assert critical_job.base_backoff_seconds == 10

        assert low_job.channel == NotificationChannelEnum.mock
        assert low_job.max_retries == 1
        assert low_job.base_backoff_seconds == 90
    finally:
        db.close()
