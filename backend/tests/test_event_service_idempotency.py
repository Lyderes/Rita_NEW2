from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base, register_models
from app.domain.enums import EventTypeEnum, SeverityEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from app.schemas.event import EventCreate
from app.services.event_service import TraceIdConflictError, create_event_with_side_effects


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


def _seed_user_device(db: Session, *, device_code: str = "idem-device-001") -> Device:
    user = User(full_name="Idempotency User")
    db.add(user)
    db.flush()
    device = Device(
        user_id=user.id,
        device_code=device_code,
        device_name="Idempotency Device",
        location_name="Salon",
        is_active=True,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def test_new_trace_id_creates_event_and_side_effects() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="idem-device-001",
        event_type=EventTypeEnum.device_offline,
        source="rita-edge",
    )

    event = create_event_with_side_effects(db, payload)
    assert event is not None
    assert db.scalar(select(func.count()).select_from(Event)) == 1
    assert db.scalar(select(func.count()).select_from(Incident)) == 1
    assert db.scalar(select(func.count()).select_from(Alert)) == 1


def test_same_trace_id_same_payload_returns_existing_event_without_duplication() -> None:
    db = _build_session()
    _seed_user_device(db)
    trace_id = uuid4()

    payload = EventCreate(
        schema_version="1.0",
        trace_id=trace_id,
        device_code="idem-device-001",
        event_type=EventTypeEnum.device_offline,
        source="rita-edge",
    )

    first = create_event_with_side_effects(db, payload)
    second = create_event_with_side_effects(db, payload)

    assert first is not None and second is not None
    assert first.id == second.id
    assert db.scalar(select(func.count()).select_from(Event)) == 1
    assert db.scalar(select(func.count()).select_from(Incident)) == 1
    assert db.scalar(select(func.count()).select_from(Alert)) == 1


def test_same_trace_id_different_payload_raises_conflict() -> None:
    db = _build_session()
    _seed_user_device(db)
    trace_id = uuid4()

    first_payload = EventCreate(
        schema_version="1.0",
        trace_id=trace_id,
        device_code="idem-device-001",
        event_type=EventTypeEnum.device_offline,
        source="rita-edge",
    )
    second_payload = EventCreate(
        schema_version="1.0",
        trace_id=trace_id,
        device_code="idem-device-001",
        event_type=EventTypeEnum.conversation_anomaly,
        source="rita-edge",
    )

    created = create_event_with_side_effects(db, first_payload)
    assert created is not None

    with pytest.raises(TraceIdConflictError):
        create_event_with_side_effects(db, second_payload)

    assert db.scalar(select(func.count()).select_from(Event)) == 1


def test_dedup_window_still_applies_for_distinct_trace_ids() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload_a = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="idem-device-001",
        event_type=EventTypeEnum.device_offline,
        severity=SeverityEnum.high,
        source="rita-edge",
    )
    payload_b = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="idem-device-001",
        event_type=EventTypeEnum.device_offline,
        severity=SeverityEnum.high,
        source="rita-edge",
    )

    first = create_event_with_side_effects(db, payload_a)
    second = create_event_with_side_effects(db, payload_b)

    assert first is not None and second is not None
    assert first.id != second.id
    assert db.scalar(select(func.count()).select_from(Event)) == 2
    assert db.scalar(select(func.count()).select_from(Incident)) == 1
    assert db.scalar(select(func.count()).select_from(Alert)) == 1
