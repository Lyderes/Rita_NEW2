from __future__ import annotations

from collections.abc import Generator
from typing import NamedTuple
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.db.session import get_db
from app.main import app
from app.models.alert import Alert
from app.models.event import Event
from app.models.incident import Incident


class ClientAndDB(NamedTuple):
    client: TestClient
    db: Session


def _event_payload(
    *,
    device_code: str,
    event_type: str,
    source: str = "rita-edge",
    user_text: str | None = None,
    trace_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "trace_id": trace_id or str(uuid4()),
        "device_code": device_code,
        "event_type": event_type,
        "source": source,
    }
    if user_text is not None:
        payload["user_text"] = user_text
    return payload


def _build_headers_for_frontend(client: TestClient) -> dict[str, str]:
    login_response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_user_and_device(client: TestClient, *, device_code: str = "e2e-device-001") -> tuple[int, str]:
    headers = _build_headers_for_frontend(client)

    user_response = client.post(
        "/users",
        json={"full_name": "E2E User", "birth_date": None, "notes": None},
        headers=headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    device_response = client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "E2E Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=headers,
    )
    assert device_response.status_code == 201
    plain_device_token = device_response.json()["device_token"]
    return user_id, plain_device_token


def _event_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Event)) or 0


def _incident_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Incident)) or 0


def _alert_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Alert)) or 0


@pytest.fixture()
def ctx() -> Generator[ClientAndDB, None, None]:
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

    app.dependency_overrides[get_db] = override_get_db
    direct_db = session_local()
    try:
        with TestClient(app) as test_client:
            yield ClientAndDB(client=test_client, db=direct_db)
    finally:
        direct_db.close()
        app.dependency_overrides.clear()


@pytest.fixture()
def client(ctx: ClientAndDB) -> TestClient:
    return ctx.client


def test_post_events_device_offline_valid_creates_event_incident_alert(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-002")
    payload = _event_payload(
        device_code="e2e-device-002",
        event_type="device_offline",
        user_text="No heartbeat from edge device",
    )

    response = ctx.client.post(
        "/events",
        json=payload,
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 201
    assert response.json()["trace_id"] == payload["trace_id"]
    assert _event_count(ctx.db) == 1
    assert _incident_count(ctx.db) == 1
    assert _alert_count(ctx.db) == 1

    persisted = ctx.db.scalar(select(Event).order_by(Event.id.desc()))
    assert persisted is not None
    assert persisted.trace_id == payload["trace_id"]


def test_post_events_device_offline_duplicate_in_window_creates_single_side_effect(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-dedup")

    payload = _event_payload(device_code="e2e-device-dedup", event_type="device_offline")

    first = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})
    second_payload = {**payload, "trace_id": str(uuid4())}
    second = ctx.client.post("/events", json=second_payload, headers={"X-Device-Token": device_token})

    assert first.status_code == 201
    assert second.status_code == 201
    assert _event_count(ctx.db) == 2
    assert _incident_count(ctx.db) == 1
    assert _alert_count(ctx.db) == 1


def test_post_events_conversation_anomaly_creates_only_event(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-anomaly")
    payload = _event_payload(
        device_code="e2e-device-anomaly",
        event_type="conversation_anomaly",
        user_text="Long silence and incoherent response",
    )

    response = ctx.client.post(
        "/events",
        json=payload,
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 201
    assert _event_count(ctx.db) == 1
    assert _incident_count(ctx.db) == 0
    assert _alert_count(ctx.db) == 0


def test_post_events_rejects_invalid_severity_for_event_type(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-semantic-severity")
    payload = _event_payload(
        device_code="e2e-device-semantic-severity",
        event_type="device_offline",
    )
    payload["severity"] = "medium"

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "unsupported severity" in detail_or_message.lower()


def test_post_events_fall_suspected_requires_confidence(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-semantic-confidence")
    payload = _event_payload(
        device_code="e2e-device-semantic-confidence",
        event_type="fall_suspected",
    )

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "missing required payload field" in detail_or_message.lower()
    assert "confidence" in detail_or_message.lower()


def test_post_events_help_request_requires_user_text_or_reason(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-semantic-help")
    payload = _event_payload(
        device_code="e2e-device-semantic-help",
        event_type="help_request",
    )

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "requires user_text or payload.reason" in detail_or_message


def test_post_events_legacy_distress_still_supported(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-legacy-distress")
    payload = _event_payload(
        device_code="e2e-device-legacy-distress",
        event_type="distress",
        user_text="Necesito ayuda",
    )

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 201
    assert _event_count(ctx.db) == 1
    assert _incident_count(ctx.db) == 0
    assert _alert_count(ctx.db) == 0


def test_post_events_internal_only_event_type_is_rejected(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-internal-type")
    payload = _event_payload(device_code="e2e-device-internal-type", event_type="device_connectivity")

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "internal-only" in detail_or_message.lower()


def test_post_events_rejects_invalid_confidence_range(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-bad-confidence")
    payload = _event_payload(
        device_code="e2e-device-bad-confidence",
        event_type="fall_suspected",
    )
    payload["payload_json"] = {"confidence": -0.1}

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "confidence must be numeric between 0 and 1" in detail_or_message


def test_post_events_rejects_invalid_pain_level(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-bad-pain-level")
    payload = _event_payload(
        device_code="e2e-device-bad-pain-level",
        event_type="pain_report",
    )
    payload["payload_json"] = {"pain_level": 0}

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "pain_level must be numeric between 1 and 10" in detail_or_message


def test_post_events_rejects_blank_keyword(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-blank-keyword")
    payload = _event_payload(
        device_code="e2e-device-blank-keyword",
        event_type="emergency_keyword_detected",
    )
    payload["payload_json"] = {"keyword": "   "}

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "keyword must be a non-empty string" in detail_or_message


def test_post_events_rejects_blank_reason(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-blank-reason")
    payload = _event_payload(
        device_code="e2e-device-blank-reason",
        event_type="help_request",
    )
    payload["payload_json"] = {"reason": "   "}

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "reason must be a non-empty string" in detail_or_message


def test_post_events_rejects_blank_required_user_text(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-blank-distress")
    payload = _event_payload(
        device_code="e2e-device-blank-distress",
        event_type="distress",
        user_text="   ",
    )

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422
    detail_or_message = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "missing required user_text" in detail_or_message.lower()


def test_post_events_invalid_device_token_returns_401(ctx: ClientAndDB) -> None:
    _create_user_and_device(ctx.client, device_code="e2e-device-bad-token")
    payload = _event_payload(device_code="e2e-device-bad-token", event_type="device_offline")

    response = ctx.client.post(
        "/events",
        json=payload,
        headers={"X-Device-Token": "wrong-token"},
    )

    assert response.status_code == 401


def test_post_events_unknown_device_code_returns_404(ctx: ClientAndDB) -> None:
    payload = _event_payload(device_code="does-not-exist", event_type="device_offline")
    response = ctx.client.post(
        "/events",
        json=payload,
        headers={"X-Device-Token": "any-token"},
    )

    assert response.status_code == 404


def test_post_events_unsupported_event_type_returns_422_not_500(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-unsupported")
    payload = _event_payload(device_code="e2e-device-unsupported", event_type="device_connectivity")

    # 'device_connectivity' is a valid enum value but internal-only, so it must be rejected as input.
    response = ctx.client.post(
        "/events",
        json=payload,
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 422
    assert response.status_code != 500
    body = response.json()
    detail_or_message = body.get("detail") or body.get("message")
    assert isinstance(detail_or_message, str)
    normalized = detail_or_message.lower()
    assert "event_type" in normalized
    assert "internal-only" in normalized or "unsupported" in normalized


def test_post_events_missing_schema_version_returns_422(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-missing-schema")
    payload = _event_payload(device_code="e2e-device-missing-schema", event_type="device_offline")
    payload.pop("schema_version")

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422


def test_post_events_wrong_schema_version_returns_422(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-bad-schema")
    payload = _event_payload(device_code="e2e-device-bad-schema", event_type="device_offline")
    payload["schema_version"] = "2.0"

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422


def test_post_events_missing_trace_id_returns_422(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-missing-trace")
    payload = _event_payload(device_code="e2e-device-missing-trace", event_type="device_offline")
    payload.pop("trace_id")

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422


def test_post_events_invalid_trace_id_returns_422(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-invalid-trace")
    payload = _event_payload(device_code="e2e-device-invalid-trace", event_type="device_offline")
    payload["trace_id"] = "not-a-uuid"

    response = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert response.status_code == 422


def test_post_events_same_trace_id_same_payload_is_idempotent(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-idempotent")
    trace_id = str(uuid4())
    payload = _event_payload(
        device_code="e2e-device-idempotent",
        event_type="device_offline",
        trace_id=trace_id,
    )

    first = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})
    second = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert _event_count(ctx.db) == 1
    assert _incident_count(ctx.db) == 1
    assert _alert_count(ctx.db) == 1


def test_post_events_same_trace_id_different_payload_returns_409(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-idempotent-conflict")
    trace_id = str(uuid4())
    first_payload = _event_payload(
        device_code="e2e-device-idempotent-conflict",
        event_type="device_offline",
        trace_id=trace_id,
    )
    conflicting_payload = _event_payload(
        device_code="e2e-device-idempotent-conflict",
        event_type="conversation_anomaly",
        trace_id=trace_id,
    )

    first = ctx.client.post("/events", json=first_payload, headers={"X-Device-Token": device_token})
    second = ctx.client.post("/events", json=conflicting_payload, headers={"X-Device-Token": device_token})

    assert first.status_code == 201
    assert second.status_code == 409
    detail_or_message = second.json().get("detail") or second.json().get("message")
    assert isinstance(detail_or_message, str)
    assert "trace_id" in detail_or_message.lower()


def test_edge_retry_reuses_same_trace_id_without_side_effect_duplication(ctx: ClientAndDB) -> None:
    _, device_token = _create_user_and_device(ctx.client, device_code="e2e-device-edge-retry")
    trace_id = str(uuid4())
    payload = _event_payload(
        device_code="e2e-device-edge-retry",
        event_type="device_offline",
        trace_id=trace_id,
        user_text="Edge retry test",
    )

    # Simulates an at-least-once delivery retry from edge queue.
    first = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})
    retry = ctx.client.post("/events", json=payload, headers={"X-Device-Token": device_token})

    assert first.status_code == 201
    assert retry.status_code == 200
    assert first.json()["id"] == retry.json()["id"]
    assert _event_count(ctx.db) == 1
    assert _incident_count(ctx.db) == 1
    assert _alert_count(ctx.db) == 1
