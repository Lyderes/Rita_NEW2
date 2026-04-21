from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum, NotificationJobStatusEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.notification_job import NotificationJob
from app.models.user import User
from app.services.data_retention_service import run_data_retention


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


def test_run_data_retention_deletes_only_old_records(monkeypatch) -> None:
    db = _make_db()
    now = datetime.now(UTC)
    
    # Mock settings to enable specific thresholds
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_data_retention", True)
    monkeypatch.setattr(settings, "data_retention_events_days", 90)
    monkeypatch.setattr(settings, "data_retention_notification_jobs_days", 30)
    monkeypatch.setattr(settings, "data_retention_closed_alerts_days", 180)

    try:
        user = User(full_name="Retention Test", notes="")
        db.add(user)
        db.flush()
        
        device = Device(user_id=user.id, device_code="device-r", device_name="Test Device", is_active=True)
        db.add(device)
        db.flush()
        
        incident_open = Incident(user_id=user.id, device_id=device.id, incident_type=EventTypeEnum.help_request, status=IncidentStatusEnum.open, severity=SeverityEnum.low)
        incident_closed = Incident(user_id=user.id, device_id=device.id, incident_type=EventTypeEnum.help_request, status=IncidentStatusEnum.closed, severity=SeverityEnum.low)
        db.add_all([incident_open, incident_closed])
        db.flush()

        # CREATE OLD RECORDS (Will be deleted)
        old_event = Event(user_id=user.id, device_id=device.id, event_type=EventTypeEnum.help_request, severity=SeverityEnum.low, trace_id="old1", created_at=now - timedelta(days=91))
        old_alert = Alert(user_id=user.id, incident_id=incident_closed.id, alert_type=EventTypeEnum.help_request, status=AlertStatusEnum.resolved, severity=SeverityEnum.low, created_at=now - timedelta(days=181), message="old")
        db.add(old_alert)
        db.flush()
        old_job = NotificationJob(alert_id=old_alert.id, status=NotificationJobStatusEnum.pending, created_at=now - timedelta(days=31))
        
        # CREATE RECENT RECORDS (Will be kept)
        recent_event = Event(user_id=user.id, device_id=device.id, event_type=EventTypeEnum.help_request, severity=SeverityEnum.low, trace_id="new1", created_at=now - timedelta(days=89))
        old_alert_unresolved = Alert(user_id=user.id, incident_id=incident_open.id, alert_type=EventTypeEnum.help_request, status=AlertStatusEnum.pending, severity=SeverityEnum.low, created_at=now - timedelta(days=181), message="keep")
        db.add(old_alert_unresolved)
        db.flush()
        recent_job = NotificationJob(alert_id=old_alert_unresolved.id, status=NotificationJobStatusEnum.pending, created_at=now - timedelta(days=29))

        db.add_all([old_event, old_job, recent_event, recent_job])
        db.commit()

        # Execute data retention
        result = run_data_retention(db, now_override=now)
        
        assert result["events_deleted"] == 1
        assert result["jobs_deleted"] == 1
        assert result["alerts_deleted"] == 1
        
        # Verify
        remaining_events = list(db.scalars(select(Event)).all())
        assert len(remaining_events) == 1
        assert remaining_events[0].id == recent_event.id
        
        remaining_jobs = list(db.scalars(select(NotificationJob)).all())
        assert len(remaining_jobs) == 1
        assert remaining_jobs[0].id == recent_job.id
        
        remaining_alerts = list(db.scalars(select(Alert)).all())
        assert len(remaining_alerts) == 1
        assert remaining_alerts[0].id == old_alert_unresolved.id
        
    finally:
        db.close()
