from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base, register_models
from app.domain.enums import EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from app.schemas.event import EventCreate
from app.services.event_service import create_event_with_side_effects


def _build_session() -> Session:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def _seed_user_device(db: Session, *, device_code: str = "rita-edge-001") -> Device:
    user = User(full_name="Test User")
    db.add(user)
    db.flush()
    device = Device(
        user_id=user.id,
        device_code=device_code,
        device_name="Test Device",
        location_name="Salon",
        is_active=True,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def test_two_falls_in_window_create_one_incident_and_one_alert() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload_1 = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rita-edge-001",
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        source="rita-edge",
        user_text="me he caido",
        rita_text="te ayudo",
        payload_json={"origin": "voice"},
    )
    payload_2 = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rita-edge-001",
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        source="rita-edge",
        user_text="me he caido otra vez",
        rita_text="te ayudo",
        payload_json={"origin": "voice"},
    )

    create_event_with_side_effects(db, payload_1)
    create_event_with_side_effects(db, payload_2)

    events_count = db.scalar(select(func.count()).select_from(Event))
    incidents_count = db.scalar(select(func.count()).select_from(Incident))
    alerts_count = db.scalar(select(func.count()).select_from(Alert))

    assert events_count == 2
    assert incidents_count == 1
    assert alerts_count == 1
    db.close()


def test_closed_incident_allows_new_fall_incident() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rita-edge-001",
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        source="rita-edge",
        user_text="me he caido",
        rita_text="te ayudo",
        payload_json={"origin": "voice"},
    )

    create_event_with_side_effects(db, payload)

    incident = db.scalar(select(Incident).order_by(Incident.id.desc()))
    assert incident is not None
    incident.status = IncidentStatusEnum.closed
    incident.closed_at = datetime.now(timezone.utc)
    db.add(incident)
    db.commit()

    first_event = db.scalar(select(Event).order_by(Event.id.asc()))
    assert first_event is not None
    first_event.created_at = datetime.now(timezone.utc) - timedelta(minutes=6)
    db.add(first_event)
    db.commit()

    create_event_with_side_effects(
        db,
        EventCreate(
            schema_version="1.0",
            trace_id=uuid4(),
            device_code="rita-edge-001",
            event_type=EventTypeEnum.fall,
            severity=SeverityEnum.high,
            source="rita-edge",
            user_text="me he caido",
            rita_text="te ayudo",
            payload_json={"origin": "voice"},
        ),
    )

    incidents_count = db.scalar(select(func.count()).select_from(Incident))
    alerts_count = db.scalar(select(func.count()).select_from(Alert))
    events_count = db.scalar(select(func.count()).select_from(Event))

    assert events_count == 2
    assert incidents_count == 2
    assert alerts_count == 2
    db.close()


def test_repeated_checkin_is_not_deduplicated_here() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rita-edge-001",
        event_type=EventTypeEnum.checkin,
        severity=SeverityEnum.low,
        source="rita-edge",
        user_text="estoy bien",
        rita_text="me alegra",
        payload_json={"origin": "voice"},
    )

    create_event_with_side_effects(db, payload)
    create_event_with_side_effects(
        db,
        EventCreate(
            schema_version="1.0",
            trace_id=uuid4(),
            device_code="rita-edge-001",
            event_type=EventTypeEnum.checkin,
            severity=SeverityEnum.low,
            source="rita-edge",
            user_text="estoy bien",
            rita_text="me alegra",
            payload_json={"origin": "voice"},
        ),
    )

    events_count = db.scalar(select(func.count()).select_from(Event))
    incidents_count = db.scalar(select(func.count()).select_from(Incident))
    alerts_count = db.scalar(select(func.count()).select_from(Alert))

    assert events_count == 2
    assert incidents_count == 0
    assert alerts_count == 0
    db.close()
