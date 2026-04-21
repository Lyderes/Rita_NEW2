from __future__ import annotations

from collections.abc import Generator
from typing import NamedTuple
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_device_token
from app.db.base import Base, register_models
from app.db.session import get_db
from app.main import app
from app.models.device import Device


class ClientAndDB(NamedTuple):
    client: TestClient
    db: Session


@pytest.fixture()
def ctx() -> Generator[ClientAndDB, None, None]:
    """Test client + direct DB session sharing the same in-memory engine."""
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


def _login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _frontend_headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(client)}"}


def _create_user_and_device(client: TestClient) -> tuple[int, str, str]:
    frontend_headers = _frontend_headers(client)
    user_response = client.post(
        "/users",
        json={"full_name": "Security User", "birth_date": None, "notes": None},
        headers=frontend_headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    device_response = client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": "secure-device-001",
            "device_name": "Secure Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=frontend_headers,
    )
    assert device_response.status_code == 201
    device_payload = device_response.json()
    return user_id, device_payload["device_code"], device_payload["device_token"]


def test_login_success_returns_bearer_token(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["access_token"]


def test_login_failure_returns_401(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_protected_frontend_endpoint_requires_jwt(client: TestClient) -> None:
    response = client.get("/dashboard")

    assert response.status_code == 401


def test_protected_frontend_endpoint_accepts_valid_jwt(client: TestClient) -> None:
    response = client.get("/dashboard", headers=_frontend_headers(client))

    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/events", "/incidents", "/alerts"])
def test_read_list_endpoints_require_jwt(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/events", "/incidents", "/alerts"])
def test_read_list_order_invalid_value_returns_422(client: TestClient, path: str) -> None:
    """order solo acepta 'asc' o 'desc'; cualquier otro valor debe devolver 422."""
    response = client.get(path, params={"order": "foobar"}, headers=_frontend_headers(client))

    assert response.status_code == 422


def test_health_remains_public(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_post_events_requires_device_token(client: TestClient) -> None:
    _, device_code, _ = _create_user_and_device(client)

    response = client.post(
        "/events",
        json={
            "schema_version": "1.0",
            "trace_id": str(uuid4()),
            "device_code": device_code,
            "event_type": "fall",
            "severity": "high",
            "source": "rita-edge",
        },
    )

    assert response.status_code == 401


def test_post_events_rejects_invalid_device_token(client: TestClient) -> None:
    _, device_code, _ = _create_user_and_device(client)

    response = client.post(
        "/events",
        json={
            "schema_version": "1.0",
            "trace_id": str(uuid4()),
            "device_code": device_code,
            "event_type": "fall",
            "severity": "high",
            "source": "rita-edge",
        },
        headers={"X-Device-Token": "wrong-token"},
    )

    assert response.status_code == 401


def test_post_events_accepts_valid_device_token(client: TestClient) -> None:
    _, device_code, device_token = _create_user_and_device(client)

    response = client.post(
        "/events",
        json={
            "schema_version": "1.0",
            "trace_id": str(uuid4()),
            "device_code": device_code,
            "event_type": "fall",
            "severity": "high",
            "source": "rita-edge",
            "user_text": "me he caido",
        },
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 201


def test_heartbeat_accepts_valid_device_token(client: TestClient) -> None:
    _, device_code, device_token = _create_user_and_device(client)

    response = client.post(
        f"/devices/{device_code}/heartbeat",
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 200
    assert response.json()["device_code"] == device_code
    assert response.json()["last_seen_at"] is not None


# ---------------------------------------------------------------------------
# Token hardening tests
# ---------------------------------------------------------------------------


def test_provision_returns_plain_token(client: TestClient) -> None:
    """The provision response must include a non-empty plain token."""
    frontend_headers = _frontend_headers(client)
    user_response = client.post(
        "/users",
        json={"full_name": "Provision User", "birth_date": None, "notes": None},
        headers=frontend_headers,
    )
    user_id = user_response.json()["id"]
    response = client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": "provision-device-001",
            "device_name": "Provision Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=frontend_headers,
    )
    payload = response.json()
    device_token = payload["device_token"]

    assert response.status_code == 201
    assert isinstance(device_token, str)
    assert len(device_token) > 0
    assert "device_token_hash" not in payload


def test_stored_value_is_hash_not_plain_token(ctx: ClientAndDB) -> None:
    """The value persisted in the DB must differ from the returned plain token."""
    _, device_code, plain_token = _create_user_and_device(ctx.client)

    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    assert device.device_token_hash is not None
    assert device.device_token_hash != plain_token
    assert device.device_token_hash == hash_device_token(plain_token)


def test_stored_value_is_sha256_hex(ctx: ClientAndDB) -> None:
    """Stored hash must be a 64-character hex string (SHA-256 digest)."""
    _, device_code, _ = _create_user_and_device(ctx.client)

    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    assert len(device.device_token_hash) == 64  # type: ignore[arg-type]
    assert all(c in "0123456789abcdef" for c in device.device_token_hash)  # type: ignore[union-attr]


def test_get_devices_does_not_expose_token_or_hash(client: TestClient) -> None:
    """GET /devices must not include device_token or device_token_hash fields."""
    _create_user_and_device(client)

    response = client.get("/devices", headers=_frontend_headers(client))
    assert response.status_code == 200
    devices = response.json()
    assert len(devices) >= 1
    for device in devices:
        assert "device_token" not in device
        assert "device_token_hash" not in device
        assert "has_device_token" in device

    def test_create_device_duplicate_code_returns_409_with_error_envelope(client: TestClient) -> None:
        frontend_headers = _frontend_headers(client)
        user_response = client.post(
            "/users",
            json={"full_name": "Duplicate Device User", "birth_date": None, "notes": None},
            headers=frontend_headers,
        )
        assert user_response.status_code == 201
        user_id = user_response.json()["id"]

        payload = {
            "user_id": user_id,
            "device_code": "dup-device-001",
            "device_name": "Duplicate Device",
            "location_name": "Salon",
            "is_active": True,
        }
        first = client.post("/devices", json=payload, headers=frontend_headers)
        second = client.post("/devices", json=payload, headers=frontend_headers)

        assert first.status_code == 201
        assert second.status_code == 409
        body = second.json()
        assert body["code"] == 409
        assert body["error"] == "conflict"
        assert body["message"] == "device_code already exists"
        assert body.get("request_id") == second.headers.get("x-request-id")


    def test_alert_acknowledge_audit_failure_returns_503_service_unavailable(
        ctx: ClientAndDB,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.api import alerts as alerts_api
        from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
        from app.models.alert import Alert
        from app.models.incident import Incident

        frontend_headers = _frontend_headers(ctx.client)
        user_response = ctx.client.post(
            "/users",
            json={"full_name": "Audit 503 User", "birth_date": None, "notes": None},
            headers=frontend_headers,
        )
        assert user_response.status_code == 201
        user_id = user_response.json()["id"]

        device_response = ctx.client.post(
            "/devices",
            json={
                "user_id": user_id,
                "device_code": "audit-503-device-001",
                "device_name": "Audit 503 Device",
                "location_name": "Salon",
                "is_active": True,
            },
            headers=frontend_headers,
        )
        assert device_response.status_code == 201
        device_id = device_response.json()["id"]

        incident = Incident(
            user_id=user_id,
            device_id=device_id,
            event_id=None,
            incident_type=EventTypeEnum.fall,
            status=IncidentStatusEnum.open,
            severity=SeverityEnum.high,
            location="Salon",
            can_call=True,
            summary="Audit 503 incident",
        )
        ctx.db.add(incident)
        ctx.db.commit()
        ctx.db.refresh(incident)

        alert = Alert(
            user_id=user_id,
            incident_id=incident.id,
            event_id=None,
            alert_type=EventTypeEnum.fall,
            severity=SeverityEnum.high,
            status=AlertStatusEnum.pending,
            message="Audit 503 alert",
        )
        ctx.db.add(alert)
        ctx.db.commit()
        ctx.db.refresh(alert)

        def _raise_audit_error(*args: object, **kwargs: object) -> None:
            raise RuntimeError("audit unavailable")

        monkeypatch.setattr(alerts_api, "record_audit_event", _raise_audit_error)
        response = ctx.client.patch(f"/alerts/{alert.id}/acknowledge", headers=frontend_headers)

        assert response.status_code == 503
        body = response.json()
        assert body["code"] == 503
        assert body["error"] == "service_unavailable"
        assert body["message"] == "Action could not be completed because required audit logging failed"
        assert body.get("request_id") == response.headers.get("x-request-id")


def test_get_devices_has_device_token_true_after_provision(client: TestClient) -> None:
    """has_device_token must be True for a provisioned device."""
    _, device_code, _ = _create_user_and_device(client)

    response = client.get("/devices", headers=_frontend_headers(client))
    assert response.status_code == 200
    device = next(d for d in response.json() if d["device_code"] == device_code)
    assert device["has_device_token"] is True


def test_rotate_token_returns_new_plain_token(client: TestClient) -> None:
    """POST /devices/{code}/rotate-token must return a new plain token."""
    _, device_code, old_token = _create_user_and_device(client)

    response = client.post(
        f"/devices/{device_code}/rotate-token",
        headers=_frontend_headers(client),
    )
    assert response.status_code == 200
    payload = response.json()
    new_token = payload["device_token"]
    assert isinstance(new_token, str)
    assert new_token != old_token
    assert "device_token_hash" not in payload


def test_rotate_token_old_token_rejected(client: TestClient) -> None:
    """After rotation, the old token must be rejected with 401."""
    _, device_code, old_token = _create_user_and_device(client)

    client.post(f"/devices/{device_code}/rotate-token", headers=_frontend_headers(client))

    response = client.post(
        "/events",
        json={
            "schema_version": "1.0",
            "trace_id": str(uuid4()),
            "device_code": device_code,
            "event_type": "fall",
            "severity": "high",
            "source": "rita-edge",
        },
        headers={"X-Device-Token": old_token},
    )
    assert response.status_code == 401


def test_rotate_token_new_token_accepted(client: TestClient) -> None:
    """After rotation, the new token must be accepted for event submission."""
    _, device_code, _ = _create_user_and_device(client)

    rotate_response = client.post(
        f"/devices/{device_code}/rotate-token",
        headers=_frontend_headers(client),
    )
    assert rotate_response.status_code == 200
    new_token = rotate_response.json()["device_token"]

    response = client.post(
        "/events",
        json={
            "schema_version": "1.0",
            "trace_id": str(uuid4()),
            "device_code": device_code,
            "event_type": "fall",
            "severity": "high",
            "source": "rita-edge",
        },
        headers={"X-Device-Token": new_token},
    )
    assert response.status_code == 201


def test_rotate_token_updates_stored_hash(ctx: ClientAndDB) -> None:
    """After rotation, the stored hash must correspond to the new plain token."""
    _, device_code, old_token = _create_user_and_device(ctx.client)

    rotate_response = ctx.client.post(
        f"/devices/{device_code}/rotate-token",
        headers=_frontend_headers(ctx.client),
    )
    new_token = rotate_response.json()["device_token"]

    ctx.db.expire_all()
    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    assert device.device_token_hash != hash_device_token(old_token)
    assert device.device_token_hash == hash_device_token(new_token)


def test_rotate_token_requires_jwt(client: TestClient) -> None:
    """POST /devices/{code}/rotate-token must reject unauthenticated requests."""
    _, device_code, _ = _create_user_and_device(client)

    response = client.post(f"/devices/{device_code}/rotate-token")
    assert response.status_code == 401
