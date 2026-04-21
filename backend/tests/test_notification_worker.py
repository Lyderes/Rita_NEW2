from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, NotificationJobStatusEnum, SeverityEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.incident import Incident
from app.models.notification_job import NotificationJob
from app.models.user import User
from app.services.notification_worker_service import run_notification_worker_once


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


def _seed_alert(db: Session, *, suffix: str) -> Alert:
    user = User(full_name=f"Worker User {suffix}", notes="worker")
    db.add(user)
    db.flush()

    device = Device(
        user_id=user.id,
        device_code=f"worker-device-{suffix}",
        device_name="Worker Device",
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
        severity=SeverityEnum.high,
        summary="Worker incident",
    )
    db.add(incident)
    db.flush()

    alert = Alert(
        user_id=user.id,
        incident_id=incident.id,
        alert_type=EventTypeEnum.assistance_needed,
        severity=SeverityEnum.high,
        status=AlertStatusEnum.pending,
        message="Worker alert",
    )
    db.add(alert)
    db.commit()
    return alert


def test_notification_worker_processes_pending_jobs_to_sent() -> None:
    db = _make_db()
    try:
        alert_ok = _seed_alert(db, suffix="ok")

        ok_job = NotificationJob(
            alert_id=alert_ok.id,
            status=NotificationJobStatusEnum.pending,
            payload_json={"message": "ok"},
        )
        db.add(ok_job)
        db.commit()

        result = run_notification_worker_once(db)

        assert result.scanned_eligible_jobs == 1
        assert result.processed_jobs == 1
        assert result.sent_jobs == 1
        assert result.rescheduled_jobs == 0
        assert result.terminal_failed_jobs == 0

        db.refresh(ok_job)

        assert ok_job.status == NotificationJobStatusEnum.sent
        assert ok_job.processed_at is not None
        assert ok_job.last_error is None
        assert ok_job.next_attempt_at is None
    finally:
        db.close()


def test_notification_worker_reschedules_failed_job_when_retries_remain() -> None:
    db = _make_db()
    now = datetime.now(UTC)
    try:
        alert_failed = _seed_alert(db, suffix="retry")
        failed_job = NotificationJob(
            alert_id=alert_failed.id,
            status=NotificationJobStatusEnum.pending,
            payload_json={"message": "fail", "force_fail": True},
            max_retries=3,
            base_backoff_seconds=5,
            retry_count=0,
        )
        db.add(failed_job)
        db.commit()

        result = run_notification_worker_once(db, now=now, base_backoff_seconds=5)

        assert result.scanned_eligible_jobs == 1
        assert result.processed_jobs == 1
        assert result.sent_jobs == 0
        assert result.rescheduled_jobs == 1
        assert result.terminal_failed_jobs == 0

        db.refresh(failed_job)
        assert failed_job.status == NotificationJobStatusEnum.pending
        assert failed_job.retry_count == 1
        assert failed_job.last_error is not None
        assert failed_job.processed_at is None
        assert failed_job.next_attempt_at is not None
        assert failed_job.next_attempt_at == (now + timedelta(seconds=5)).replace(tzinfo=None)

        second = run_notification_worker_once(db, now=now + timedelta(seconds=1), base_backoff_seconds=5)
        assert second.scanned_eligible_jobs == 0

        third = run_notification_worker_once(db, now=now + timedelta(seconds=6), base_backoff_seconds=5)
        assert third.scanned_eligible_jobs == 1
    finally:
        db.close()


def test_push_job_without_fcm_token_is_rescheduled() -> None:
    """A push job with no fcm_token in the payload must fail and reschedule,
    not be silently marked as sent with a dummy token."""
    db = _make_db()
    try:
        alert = _seed_alert(db, suffix="no-token")
        job = NotificationJob(
            alert_id=alert.id,
            status=NotificationJobStatusEnum.pending,
            channel="push",
            payload_json={"message": "no token here"},  # no fcm_token key
            max_retries=3,
        )
        db.add(job)
        db.commit()

        result = run_notification_worker_once(db)

        assert result.sent_jobs == 0
        assert result.rescheduled_jobs == 1

        db.refresh(job)
        assert job.status == NotificationJobStatusEnum.pending
        assert job.last_error is not None
        assert "FCM token" in job.last_error
    finally:
        db.close()


def test_notification_worker_marks_failed_terminal_when_retry_limit_exceeded() -> None:
    db = _make_db()
    now = datetime.now(UTC)
    try:
        alert_failed = _seed_alert(db, suffix="terminal")
        failed_job = NotificationJob(
            alert_id=alert_failed.id,
            status=NotificationJobStatusEnum.pending,
            payload_json={"message": "fail", "force_fail": True},
            max_retries=1,
            retry_count=1,
            next_attempt_at=now - timedelta(seconds=1),
        )
        db.add(failed_job)
        db.commit()

        result = run_notification_worker_once(db, now=now, base_backoff_seconds=5)

        assert result.scanned_eligible_jobs == 1
        assert result.processed_jobs == 1
        assert result.sent_jobs == 0
        assert result.rescheduled_jobs == 0
        assert result.terminal_failed_jobs == 1

        db.refresh(failed_job)
        assert failed_job.status == NotificationJobStatusEnum.failed
        assert failed_job.retry_count == 2
        assert failed_job.last_error is not None
        assert failed_job.processed_at is not None
        assert failed_job.next_attempt_at is None
    finally:
        db.close()
