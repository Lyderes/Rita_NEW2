from __future__ import annotations

from collections.abc import Generator
from typing import Any, NamedTuple, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.db.session import get_db
from app.domain.enums import DeviceAdminStatusEnum
from app.main import app
from app.models.device import Device
from app.services.metrics_service import reset_metrics


class ClientAndDB(NamedTuple):
    client: TestClient
    db: Session


@pytest.fixture()
def ctx() -> Generator[ClientAndDB, None, None]:
    register_models()
    reset_metrics()
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
        reset_metrics()


def _frontend_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_user_and_device(client: TestClient, *, device_code: str) -> tuple[int, str]:
    headers = _frontend_headers(client)
    user_response = client.post(
        "/users",
        json={"full_name": "Metrics User", "birth_date": None, "notes": None},
        headers=headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    device_response = client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "Metrics Device",
            "location_name": "Lab",
            "is_active": True,
        },
        headers=headers,
    )
    assert device_response.status_code == 201
    return user_id, device_response.json()["device_token"]


def _event_payload(device_code: str, *, event_type: str = "help_request", trace_id: str | None = None) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "trace_id": trace_id or str(uuid4()),
        "device_code": device_code,
        "event_type": event_type,
        "severity": "high",
        "source": "test",
        "user_text": "Necesito ayuda",
    }


def _metrics_summary(client: TestClient) -> dict[str, object]:
    response = client.get("/metrics/summary", headers=_frontend_headers(client))
    assert response.status_code == 200
    return response.json()


def test_metrics_summary_requires_frontend_auth(ctx: ClientAndDB) -> None:
    response = ctx.client.get("/metrics/summary")
    assert response.status_code == 401


def test_event_counters_received_semantic_rejected_and_replay(ctx: ClientAndDB) -> None:
    device_code = "metrics-events-001"
    _, device_token = _create_user_and_device(ctx.client, device_code=device_code)

    semantic_invalid = _event_payload(device_code, event_type="fall_suspected")
    semantic_invalid.pop("user_text", None)
    semantic_invalid.pop("severity", None)
    response_rejected = ctx.client.post(
        "/events",
        json=semantic_invalid,
        headers={"X-Device-Token": device_token},
    )
    assert response_rejected.status_code == 422

    trace_id = str(uuid4())
    valid_payload = _event_payload(device_code, trace_id=trace_id)
    response_first = ctx.client.post("/events", json=valid_payload, headers={"X-Device-Token": device_token})
    assert response_first.status_code == 201

    response_replay = ctx.client.post("/events", json=valid_payload, headers={"X-Device-Token": device_token})
    assert response_replay.status_code == 200

    summary = _metrics_summary(ctx.client)
    counters = cast(dict[str, int], summary["counters"])
    assert counters["events_received_total"] == 3
    assert counters["events_rejected_semantic_total"] == 1
    assert counters["events_idempotent_replay_total"] == 1
    assert counters["incidents_created_total"] == 1
    assert counters["alerts_created_total"] == 1


def test_device_auth_and_forbidden_counters(ctx: ClientAndDB) -> None:
    device_code = "metrics-auth-001"
    _, device_token = _create_user_and_device(ctx.client, device_code=device_code)

    missing_header_response = ctx.client.post("/events", json=_event_payload(device_code))
    assert missing_header_response.status_code == 401

    invalid_token_response = ctx.client.post(
        "/events",
        json=_event_payload(device_code),
        headers={"X-Device-Token": "invalid-token"},
    )
    assert invalid_token_response.status_code == 401

    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    device.admin_status = DeviceAdminStatusEnum.suspended
    device.admin_status_reason = "manual lock"
    ctx.db.add(device)
    ctx.db.commit()

    forbidden_response = ctx.client.post(
        "/events",
        json=_event_payload(device_code),
        headers={"X-Device-Token": device_token},
    )
    assert forbidden_response.status_code == 403

    summary = _metrics_summary(ctx.client)
    counters = cast(dict[str, int], summary["counters"])
    assert counters["device_auth_failed_total"] == 2
    assert counters["device_forbidden_total"] == 1


def test_audit_required_failure_counter(ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import devices as devices_api

    headers = _frontend_headers(ctx.client)
    user_response = ctx.client.post(
        "/users",
        json={"full_name": "Audit Metrics User", "birth_date": None, "notes": None},
        headers=headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(devices_api, "record_audit_event", _raise_audit_error)

    create_response = ctx.client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": "metrics-audit-001",
            "device_name": "Audit Metrics Device",
            "location_name": "Lab",
            "is_active": True,
        },
        headers=headers,
    )
    assert create_response.status_code == 503

    summary = _metrics_summary(ctx.client)
    counters = cast(dict[str, int], summary["counters"])
    assert counters["audit_required_failure_total"] == 1


def test_http_metrics_are_recorded(ctx: ClientAndDB) -> None:
    health_response = ctx.client.get("/health")
    assert health_response.status_code == 200

    summary = _metrics_summary(ctx.client)
    http_requests = cast(list[dict[str, Any]], summary["http_requests_total"])
    durations = cast(list[dict[str, Any]], summary["http_request_duration_ms"])

    health_rows = [item for item in http_requests if item["endpoint"] == "/health" and item["status_code"] == 200]
    assert health_rows
    assert health_rows[0]["count"] >= 1

    health_duration_rows = [item for item in durations if item["endpoint"] == "/health"]
    assert health_duration_rows
    assert health_duration_rows[0]["count"] >= 1
    assert health_duration_rows[0]["max_ms"] >= health_duration_rows[0]["min_ms"]
