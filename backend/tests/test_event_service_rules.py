from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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
from app.services.event_service import EventSemanticValidationError, create_event_with_side_effects


def _build_session() -> Session:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return session_local()


def _seed_user_device(db: Session, *, device_code: str = "rules-device-001") -> Device:
    user = User(full_name="Rules User")
    db.add(user)
    db.flush()

    device = Device(
        user_id=user.id,
        device_code=device_code,
        device_name="Rules Device",
        location_name="Salon",
        is_active=True,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def test_device_offline_creates_incident_and_alert() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.device_offline,
        source="rita-edge",
        user_text="No se detecta el dispositivo",
    )

    event = create_event_with_side_effects(db, payload)
    assert event is not None

    incidents = db.scalars(select(Incident)).all()
    alerts = db.scalars(select(Alert)).all()

    assert len(incidents) == 1
    assert len(alerts) == 1
    assert incidents[0].incident_type == EventTypeEnum.device_connectivity
    assert incidents[0].severity == SeverityEnum.high
    assert alerts[0].incident_id == incidents[0].id


def test_device_offline_duplicate_does_not_create_new_incident() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.device_offline,
        source="rita-edge",
    )

    first_event = create_event_with_side_effects(db, payload)
    assert first_event is not None

    second_event = create_event_with_side_effects(
        db,
        EventCreate(
            schema_version="1.0",
            trace_id=uuid4(),
            device_code="rules-device-001",
            event_type=EventTypeEnum.device_offline,
            source="rita-edge",
        ),
    )
    assert second_event is not None

    events_count = db.scalar(select(func.count()).select_from(Event))
    incidents_count = db.scalar(select(func.count()).select_from(Incident))
    alerts_count = db.scalar(select(func.count()).select_from(Alert))

    assert events_count == 2
    assert incidents_count == 1
    assert alerts_count == 1


def test_conversation_anomaly_creates_event_only() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.conversation_anomaly,
        source="rita-edge",
        user_text="Conversacion irregular detectada",
    )

    event = create_event_with_side_effects(db, payload)
    assert event is not None

    assert db.scalar(select(func.count()).select_from(Event)) == 1
    assert db.scalar(select(func.count()).select_from(Incident)) == 0
    assert db.scalar(select(func.count()).select_from(Alert)) == 0
    assert event.severity == SeverityEnum.low


def test_fall_suspected_creates_critical_incident() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.fall_suspected,
        source="rita-edge",
        user_text="Posible caida detectada",
        payload_json={"confidence": 0.93},
    )

    event = create_event_with_side_effects(db, payload)
    assert event is not None

    incident = db.scalar(select(Incident).order_by(Incident.id.desc()))
    assert incident is not None
    assert incident.incident_type == EventTypeEnum.possible_fall
    assert incident.severity == SeverityEnum.critical
    assert event.severity == SeverityEnum.critical


def test_device_offline_dedup_expires_after_window() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.device_offline,
        source="rita-edge",
    )

    first_event = create_event_with_side_effects(db, payload)
    assert first_event is not None

    first_event.created_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db.add(first_event)
    db.commit()

    second_event = create_event_with_side_effects(
        db,
        EventCreate(
            schema_version="1.0",
            trace_id=uuid4(),
            device_code="rules-device-001",
            event_type=EventTypeEnum.device_offline,
            source="rita-edge",
        ),
    )
    assert second_event is not None

    assert db.scalar(select(func.count()).select_from(Incident)) == 2
    assert db.scalar(select(func.count()).select_from(Alert)) == 2


def test_logs_include_trace_id_for_event_and_side_effects(caplog: pytest.LogCaptureFixture) -> None:
    db = _build_session()
    _seed_user_device(db)
    trace_id = str(uuid4())

    payload = EventCreate(
        schema_version="1.0",
        trace_id=trace_id,
        device_code="rules-device-001",
        event_type=EventTypeEnum.device_offline,
        source="rita-edge",
    )

    with caplog.at_level(logging.INFO, logger="app.services.event_service"):
        create_event_with_side_effects(db, payload)

    records = [r for r in caplog.records if r.name == "app.services.event_service"]
    messages = {r.getMessage() for r in records}
    assert "event_received" in messages
    assert "incident_created" in messages
    assert "alert_created" in messages

    trace_values = [getattr(r, "trace_id", None) for r in records]
    assert trace_id in trace_values


def test_device_offline_rejects_invalid_severity() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.device_offline,
        severity=SeverityEnum.medium,
        source="rita-edge",
    )

    with pytest.raises(EventSemanticValidationError, match="unsupported severity"):
        create_event_with_side_effects(db, payload)


def test_fall_suspected_requires_confidence_in_payload() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.fall_suspected,
        source="rita-edge",
    )

    with pytest.raises(EventSemanticValidationError, match="missing required payload field: confidence"):
        create_event_with_side_effects(db, payload)


def test_help_request_requires_user_text_or_payload_reason() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.help_request,
        source="rita-edge",
    )

    with pytest.raises(EventSemanticValidationError, match="help_request requires user_text or payload.reason"):
        create_event_with_side_effects(db, payload)


def test_legacy_distress_event_remains_supported() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.distress,
        severity=SeverityEnum.medium,
        source="rita-edge",
        user_text="Necesito ayuda",
    )

    event = create_event_with_side_effects(db, payload)
    assert event is not None
    assert event.event_type == EventTypeEnum.distress
    assert db.scalar(select(func.count()).select_from(Incident)) == 0
    assert db.scalar(select(func.count()).select_from(Alert)) == 0


def test_fall_suspected_rejects_out_of_range_confidence() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.fall_suspected,
        source="rita-edge",
        payload_json={"confidence": 1.4},
    )

    with pytest.raises(EventSemanticValidationError, match="confidence must be numeric between 0 and 1"):
        create_event_with_side_effects(db, payload)


def test_pain_report_rejects_invalid_pain_level() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.pain_report,
        source="rita-edge",
        payload_json={"pain_level": 11},
    )

    with pytest.raises(EventSemanticValidationError, match="pain_level must be numeric between 1 and 10"):
        create_event_with_side_effects(db, payload)


def test_emergency_keyword_detected_rejects_blank_keyword() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.emergency_keyword_detected,
        source="rita-edge",
        payload_json={"keyword": "   "},
    )

    with pytest.raises(EventSemanticValidationError, match="keyword must be a non-empty string"):
        create_event_with_side_effects(db, payload)


def test_help_request_rejects_blank_reason() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.help_request,
        source="rita-edge",
        payload_json={"reason": "   "},
    )

    with pytest.raises(EventSemanticValidationError, match="reason must be a non-empty string"):
        create_event_with_side_effects(db, payload)


def test_distress_requires_non_empty_user_text() -> None:
    db = _build_session()
    _seed_user_device(db)

    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="rules-device-001",
        event_type=EventTypeEnum.distress,
        source="rita-edge",
        user_text="   ",
    )

    with pytest.raises(EventSemanticValidationError, match="missing required user_text"):
        create_event_with_side_effects(db, payload)
