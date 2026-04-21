from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, NotificationJobStatusEnum, SeverityEnum
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification_job import NotificationJob

from app.schemas.event import EventCreate
from app.services.event_service import create_event_with_side_effects
from app.services.alert_escalation_service import run_alert_escalation_once
from app.services.notification_worker_service import run_notification_worker_once




@patch("app.services.notifications.providers.twilio_provider.Client")
@patch("app.services.notifications.providers.fcm_provider.messaging.send")
def test_e2e_happy_path(mock_fcm_send, mock_twilio_client, db_session: Session, monkeypatch) -> None:
    # 1. Clear settings cache and reset global providers to respect monkeypatch
    from app.core.config import get_settings
    get_settings.cache_clear()
    
    import app.services.notification_worker_service as worker_mod
    worker_mod._fcm_provider = None
    worker_mod._twilio_provider = None

    # Mocks configuration ensuring channel mapping will occur
    mock_fcm_send.return_value = "fcm_mock_id"
    import firebase_admin
    monkeypatch.setattr(firebase_admin, "_apps", {"[DEFAULT]": True})
    
    # 2. INGESTION
    payload = EventCreate(
        schema_version="1.0",
        trace_id=str(uuid.uuid4()),
        device_code="e2e-device-01",
        event_type=EventTypeEnum.fall_suspected, # opens incident, creates alert
        severity=SeverityEnum.critical, # maps to SMS channel realistically
        source="e2e-suite",
        payload_json={"confidence": 0.95, "phone_number": "+1234"}
    )
    event = create_event_with_side_effects(db_session, payload)
    assert event is not None
    # Backdate to bypass the 1-minute safety window in run_alert_escalation_once
    event.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.add(event)
    db_session.commit()
    
    # Verify DB Side effects
    incident = db_session.scalar(select(Incident).where(Incident.event_id == event.id))
    assert incident is not None
    assert incident.status == IncidentStatusEnum.open
    
    alert = db_session.scalar(select(Alert).where(Alert.incident_id == incident.id))
    assert alert is not None
    
    now_ts = datetime.now(UTC)
    alert.created_at = now_ts - timedelta(hours=24)
    db_session.add(alert)
    db_session.commit()
    
    assert alert.status == AlertStatusEnum.pending
    
    # 3. ESCALATION (Alert -> Job)
    escalation_result = run_alert_escalation_once(db_session, now=now_ts, pending_threshold_minutes=0)
    assert escalation_result.notification_jobs_created > 0
    
    job = db_session.scalar(select(NotificationJob).where(NotificationJob.alert_id == alert.id))
    assert job is not None
    assert job.status == NotificationJobStatusEnum.pending
    
    # 4. WORKER PROCESSING (Job -> Sent via Twilio because critical)
    mock_twilio_instance = MagicMock()
    mock_twilio_client.return_value = mock_twilio_instance
    mock_twilio_msg = MagicMock()
    mock_twilio_msg.sid = "SM_E2E"
    mock_twilio_instance.messages.create.return_value = mock_twilio_msg
    
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth123")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+1234567890")

    worker_result = run_notification_worker_once(db_session, batch_size=10)
    assert worker_result.sent_jobs > 0
    
    # Verify final Job state
    db_session.refresh(job)
    assert job.status == NotificationJobStatusEnum.sent
    assert job.provider_response == "SM_E2E"


def test_e2e_deduplication(db_session: Session) -> None:
    # First payload (pain_report has 10m dedup window)
    payload1 = EventCreate(
        schema_version="1.0",
        trace_id=str(uuid.uuid4()),
        device_code="e2e-device-01",
        event_type=EventTypeEnum.pain_report,
        severity=SeverityEnum.medium,
        payload_json={"pain_level": 5},
        source="e2e-suite"
    )
    event1 = create_event_with_side_effects(db_session, payload1)
    
    # Second payload (duplicate within Dedup Window)
    payload2 = EventCreate(
        schema_version="1.0",
        trace_id=str(uuid.uuid4()),
        device_code="e2e-device-01",
        event_type=EventTypeEnum.pain_report,
        severity=SeverityEnum.medium,
        payload_json={"pain_level": 6},
        source="e2e-suite"
    )
    event2 = create_event_with_side_effects(db_session, payload2)
    
    # Verify Event 1 created Incident
    assert db_session.scalar(select(Incident).where(Incident.event_id == event1.id)) is not None
    
    # Verify Event 2 was recorded but created NO incident due to deduplication
    assert event2 is not None
    assert db_session.scalar(select(Incident).where(Incident.event_id == event2.id)) is None


def test_e2e_ack_halts_escalation(db_session: Session) -> None:
    # Ingest
    payload = EventCreate(
        schema_version="1.0",
        trace_id=str(uuid.uuid4()),
        device_code="e2e-device-01",
        event_type=EventTypeEnum.help_request,
        severity=SeverityEnum.high,
        user_text="help me ack",
        source="e2e-suite"
    )
    event = create_event_with_side_effects(db_session, payload)
    
    alert = db_session.scalar(select(Alert).where(Alert.event_id == event.id))
    alert.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.add(alert)
    db_session.commit()
    
    # SIMULATE ACK: someone marks the alert as resolved before escalation
    alert.status = AlertStatusEnum.resolved
    db_session.add(alert)
    db_session.commit()
    
    # ESCALATION
    escalation_result = run_alert_escalation_once(db_session, now=datetime.now(UTC), pending_threshold_minutes=0)
    
    # Verify NO job was created because alert was already resolved
    assert escalation_result.notification_jobs_created == 0
    assert db_session.scalar(select(NotificationJob).where(NotificationJob.alert_id == alert.id)) is None


@patch("app.services.notifications.providers.fcm_provider.messaging.send")
def test_e2e_provider_failure_with_retry(mock_fcm_send, db_session: Session, monkeypatch) -> None:
    # Clear settings cache and reset global providers
    from app.core.config import get_settings
    get_settings.cache_clear()
    import app.services.notification_worker_service as worker_mod
    worker_mod._fcm_provider = None
    worker_mod._twilio_provider = None

    # Force provider to raise an exception
    mock_fcm_send.side_effect = Exception("FCM Network Timeout Simulation")
    import firebase_admin
    monkeypatch.setattr(firebase_admin, "_apps", {"[DEFAULT]": True})
    
    # Ingest (medium severity usually maps to push channel)
    payload = EventCreate(
        schema_version="1.0",
        trace_id=str(uuid.uuid4()),
        device_code="e2e-device-01",
        event_type=EventTypeEnum.help_request,
        severity=SeverityEnum.high,
        user_text="retry test",
        source="e2e-suite"
    )
    event = create_event_with_side_effects(db_session, payload)
    alert = db_session.scalar(select(Alert).where(Alert.event_id == event.id))
    alert.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.add(alert)
    db_session.commit()
    escalation_result = run_alert_escalation_once(db_session, now=datetime.now(UTC), pending_threshold_minutes=0)
    assert escalation_result.notification_jobs_created > 0
    
    alert = db_session.scalar(select(Alert).where(Alert.event_id == event.id))
    job = db_session.scalar(select(NotificationJob).where(NotificationJob.alert_id == alert.id))
    assert job is not None
    
    # WORKER RUN 1
    worker_result = run_notification_worker_once(db_session, batch_size=10)
    
    db_session.refresh(job)
    # The provider failed, so status should be 'pending' but with retry_count incremented
    assert worker_result.rescheduled_jobs > 0
    assert job.status == NotificationJobStatusEnum.pending
    assert job.retry_count == 1
    assert "FCM Network Timeout Simulation" in job.last_error
    assert job.next_attempt_at is not None
