from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from app.services.heartbeat_monitor_service import run_heartbeat_monitor_once


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


def test_heartbeat_monitor_creates_device_offline_event_and_side_effects() -> None:
    db = _make_db()
    now = datetime.now(UTC)
    try:
        user = User(full_name="Heartbeat User", notes="heartbeat")
        db.add(user)
        db.flush()

        device = Device(
            user_id=user.id,
            device_code=f"hb-device-{uuid4()}",
            device_name="HB Device",
            location_name="Lab",
            is_active=True,
            last_seen_at=now - timedelta(minutes=61),
        )
        db.add(device)
        db.commit()

        result = run_heartbeat_monitor_once(db, now=now, source="test-heartbeat-monitor")

        assert result.scanned_devices == 1
        assert result.offline_candidates == 1
        assert result.events_created == 1
        assert result.idempotent_replays == 0

        event = db.scalar(select(Event).where(Event.device_id == device.id).order_by(Event.id.desc()))
        assert event is not None
        assert event.event_type == EventTypeEnum.device_offline

        incident = db.scalar(select(Incident).where(Incident.event_id == event.id))
        assert incident is not None
        assert incident.status == IncidentStatusEnum.open

        alert = db.scalar(select(Alert).where(Alert.event_id == event.id))
        assert alert is not None
        assert alert.status == AlertStatusEnum.pending
    finally:
        db.close()


def test_heartbeat_monitor_is_idempotent_in_same_window() -> None:
    db = _make_db()
    now = datetime.now(UTC)
    try:
        user = User(full_name="Heartbeat User 2", notes="heartbeat")
        db.add(user)
        db.flush()

        device = Device(
            user_id=user.id,
            device_code=f"hb-device-{uuid4()}",
            device_name="HB Device 2",
            location_name="Lab",
            is_active=True,
            last_seen_at=now - timedelta(minutes=70),
        )
        db.add(device)
        db.commit()

        first = run_heartbeat_monitor_once(db, now=now)
        second = run_heartbeat_monitor_once(db, now=now + timedelta(minutes=1))

        assert first.events_created == 1
        assert second.events_created == 0
        assert second.idempotent_replays == 1

        event_count = db.scalar(select(func.count()).select_from(Event).where(Event.device_id == device.id))
        incident_count = db.scalar(select(func.count()).select_from(Incident).where(Incident.device_id == device.id))
        alert_count = db.scalar(
            select(func.count())
            .select_from(Alert)
            .join(Incident, Incident.id == Alert.incident_id)
            .where(Incident.device_id == device.id)
        )

        assert event_count == 1
        assert incident_count == 1
        assert alert_count == 1
    finally:
        db.close()
