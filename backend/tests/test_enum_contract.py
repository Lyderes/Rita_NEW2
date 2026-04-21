from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import authenticate_device_for_event, require_frontend_auth
from app.db.base import Base, register_models
from app.db.session import get_db
from app.domain.event_catalog import (
    CANONICAL_INPUT_EVENT_TYPES,
    DERIVED_INTERNAL_EVENT_TYPES,
    LEGACY_INPUT_EVENT_TYPES,
    get_input_event_rule,
)
from app.domain.enums import EventTypeEnum, SeverityEnum
from app.main import app
from app.models.device import Device
from app.schemas.event import EventCreate


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    def override_device_auth(payload: EventCreate, db: Session = Depends(get_db)) -> Device:
        device = db.scalar(select(Device).where(Device.device_code == payload.device_code))
        assert device is not None
        return device

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_frontend_auth] = lambda: "test-frontend"
    app.dependency_overrides[authenticate_device_for_event] = override_device_auth
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _create_user_and_device(client: TestClient, *, device_code: str = "enum-device-001") -> None:
    user_response = client.post(
        "/users",
        json={"full_name": "Enum Test User", "birth_date": None, "notes": None},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    device_response = client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "Enum Device",
            "location_name": "Salon",
            "is_active": True,
        },
    )
    assert device_response.status_code == 201


def test_event_create_accepts_valid_enum_values() -> None:
    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code="enum-device-001",
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
    )

    assert payload.event_type == EventTypeEnum.fall
    assert payload.severity == SeverityEnum.high


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("event_type", "invalid_event"),
        ("severity", "urgent"),
    ],
)
def test_event_create_rejects_invalid_enum_values(field_name: str, field_value: str) -> None:
    payload = {
        "schema_version": "1.0",
        "trace_id": str(uuid4()),
        "device_code": "enum-device-001",
        "event_type": EventTypeEnum.fall.value,
        "severity": SeverityEnum.high.value,
    }
    payload[field_name] = field_value

    with pytest.raises(ValidationError):
        EventCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/events",
            {
                "schema_version": "1.0",
                "trace_id": str(uuid4()),
                "device_code": "enum-device-001",
                "event_type": "invalid_event",
                "severity": SeverityEnum.high.value,
                "source": "rita-edge",
            },
        ),
        (
            "/events",
            {
                "schema_version": "1.0",
                "trace_id": str(uuid4()),
                "device_code": "enum-device-001",
                "event_type": EventTypeEnum.fall.value,
                "severity": "urgent",
                "source": "rita-edge",
            },
        ),
    ],
)
def test_post_events_invalid_enum_values_return_422(
    client: TestClient,
    path: str,
    payload: dict[str, str],
) -> None:
    _create_user_and_device(client)

    response = client.post(path, json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/events?severity=valor_invalido",
        "/incidents?status=valor_invalido",
        "/incidents?severity=valor_invalido",
        "/alerts?status=valor_invalido",
        "/alerts?severity=valor_invalido",
    ],
)
def test_invalid_enum_query_params_return_422(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 422


def test_enum_fields_serialize_as_plain_strings_in_api_json(client: TestClient) -> None:
    _create_user_and_device(client)

    event_response = client.post(
        "/events",
        json={
            "schema_version": "1.0",
            "trace_id": str(uuid4()),
            "device_code": "enum-device-001",
            "event_type": EventTypeEnum.fall.value,
            "severity": SeverityEnum.high.value,
            "source": "rita-edge",
            "user_text": "me he caido",
            "rita_text": "te ayudo",
            "payload_json": {"origin": "test"},
        },
    )
    assert event_response.status_code == 201

    event_json = event_response.json()
    assert event_json["event_type"] == "fall"
    assert isinstance(event_json["event_type"], str)
    assert event_json["severity"] == "high"
    assert isinstance(event_json["severity"], str)

    incidents_response = client.get("/incidents")
    assert incidents_response.status_code == 200
    incidents_payload = incidents_response.json()
    assert "items" in incidents_payload
    incident_json = incidents_payload["items"][0]
    assert incident_json["incident_type"] == "fall"
    assert isinstance(incident_json["incident_type"], str)
    assert incident_json["severity"] == "high"
    assert isinstance(incident_json["severity"], str)
    assert incident_json["status"] == "open"
    assert isinstance(incident_json["status"], str)

    alerts_response = client.get("/alerts")
    assert alerts_response.status_code == 200
    alerts_payload = alerts_response.json()
    assert "items" in alerts_payload
    alert_json = alerts_payload["items"][0]
    assert alert_json["alert_type"] == "fall"
    assert isinstance(alert_json["alert_type"], str)
    assert alert_json["severity"] == "high"
    assert isinstance(alert_json["severity"], str)
    assert alert_json["status"] == "pending"
    assert isinstance(alert_json["status"], str)


def test_event_type_classification_is_complete_and_disjoint() -> None:
    all_classified = CANONICAL_INPUT_EVENT_TYPES | LEGACY_INPUT_EVENT_TYPES | DERIVED_INTERNAL_EVENT_TYPES

    assert not (CANONICAL_INPUT_EVENT_TYPES & LEGACY_INPUT_EVENT_TYPES)
    assert not (CANONICAL_INPUT_EVENT_TYPES & DERIVED_INTERNAL_EVENT_TYPES)
    assert not (LEGACY_INPUT_EVENT_TYPES & DERIVED_INTERNAL_EVENT_TYPES)
    assert all_classified == frozenset(EventTypeEnum)


def test_derived_internal_event_types_have_no_input_rule() -> None:
    for event_type in DERIVED_INTERNAL_EVENT_TYPES:
        assert get_input_event_rule(event_type) is None


def test_canonical_and_legacy_event_types_have_input_rule() -> None:
    for event_type in CANONICAL_INPUT_EVENT_TYPES | LEGACY_INPUT_EVENT_TYPES:
        assert get_input_event_rule(event_type) is not None