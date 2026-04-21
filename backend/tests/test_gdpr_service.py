from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from app.services.gdpr_service import UserNotFoundError, execute_right_to_be_forgotten


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


def _seed_user_with_data(db: Session) -> tuple[User, Device, Event, Incident, Alert]:
    user = User(full_name="Delete Me", notes="test user")
    db.add(user)
    db.flush()

    device = Device(user_id=user.id, device_code="device-x", device_name="Test Device", is_active=True)
    db.add(device)
    db.flush()

    event = Event(user_id=user.id, device_id=device.id, event_type=EventTypeEnum.help_request, severity=SeverityEnum.high, trace_id="trace1")
    db.add(event)
    db.flush()

    incident = Incident(user_id=user.id, device_id=device.id, incident_type=EventTypeEnum.help_request, status=IncidentStatusEnum.open, severity=SeverityEnum.high)
    db.add(incident)
    db.flush()

    alert = Alert(user_id=user.id, incident_id=incident.id, alert_type=EventTypeEnum.help_request, status=AlertStatusEnum.pending, severity=SeverityEnum.high, message="Alert")
    db.add(alert)
    db.commit()
    return user, device, event, incident, alert


def test_right_to_be_forgotten_cascades_deletions() -> None:
    db = _make_db()
    try:
        user, device, event, incident, alert = _seed_user_with_data(db)
        user_id = user.id

        result = execute_right_to_be_forgotten(db, user_id)

        assert result["action"] == "gdpr_right_to_be_forgotten"
        assert result["user_id"] == user_id
        assert result["user_name"] == "Delete Me"
        assert "deleted_at" in result
        assert "deleted_counts" in result

        assert db.get(User, user_id) is None
        assert db.get(Device, device.id) is None
        assert db.get(Event, event.id) is None
        assert db.get(Incident, incident.id) is None
        assert db.get(Alert, alert.id) is None
    finally:
        db.close()


def test_right_to_be_forgotten_writes_audit_log() -> None:
    db = _make_db()
    try:
        user, *_ = _seed_user_with_data(db)
        user_id = user.id
        user_name = user.full_name

        execute_right_to_be_forgotten(db, user_id)

        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action_type == "gdpr_right_to_be_forgotten",
                AuditLog.target_identifier == str(user_id),
            )
        )
        assert audit is not None
        assert audit.target_type == "user"
        assert audit.actor_type == "frontend_user"
        assert audit.metadata_json is not None
        assert audit.metadata_json["user_name"] == user_name
        assert "deleted_counts" in audit.metadata_json
    finally:
        db.close()


def test_right_to_be_forgotten_deleted_counts_are_accurate() -> None:
    db = _make_db()
    try:
        user, _, event, incident, alert = _seed_user_with_data(db)
        user_id = user.id

        result = execute_right_to_be_forgotten(db, user_id)

        counts = result["deleted_counts"]
        assert counts["devices"] == 1
        assert counts["events"] == 1
        assert counts["incidents"] == 1
        assert counts["alerts"] == 1
    finally:
        db.close()


def test_right_to_be_forgotten_user_not_found() -> None:
    db = _make_db()
    try:
        with pytest.raises(UserNotFoundError):
            execute_right_to_be_forgotten(db, 99999)
    finally:
        db.close()
