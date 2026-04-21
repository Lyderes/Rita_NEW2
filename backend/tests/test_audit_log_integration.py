from __future__ import annotations

from collections.abc import Generator
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.db.base import Base, register_models
from app.db.session import get_db
from app.main import app
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.incident import Incident
from app.models.user import User


class ClientAndDB(NamedTuple):
    client: TestClient
    db: Session


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


def _frontend_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _count_audit(db: Session, action_type: str) -> int:
    stmt = select(func.count()).select_from(AuditLog).where(AuditLog.action_type == action_type)
    return db.scalar(stmt) or 0


def _latest_audit(db: Session, action_type: str) -> AuditLog | None:
    stmt = select(AuditLog).where(AuditLog.action_type == action_type).order_by(AuditLog.id.desc())
    return db.scalar(stmt)


def _get_device_by_code(db: Session, device_code: str) -> Device | None:
    return db.scalar(select(Device).where(Device.device_code == device_code))


def _seed_user_device_incident_alert(ctx: ClientAndDB) -> tuple[User, Device, Incident, Alert]:
    user = User(full_name="Audit State User", birth_date=None, notes=None)
    ctx.db.add(user)
    ctx.db.commit()
    ctx.db.refresh(user)

    device = Device(
        user_id=user.id,
        device_code="audit-state-device-001",
        device_token_hash=None,
        device_name="Audit State Device",
        location_name="Salon",
        is_active=True,
    )
    ctx.db.add(device)
    ctx.db.commit()
    ctx.db.refresh(device)

    incident = Incident(
        user_id=user.id,
        device_id=device.id,
        event_id=None,
        incident_type=EventTypeEnum.fall,
        status=IncidentStatusEnum.open,
        severity=SeverityEnum.high,
        location="Salon",
        can_call=True,
        summary="Incident for audit failure tests",
    )
    ctx.db.add(incident)
    ctx.db.commit()
    ctx.db.refresh(incident)

    alert = Alert(
        user_id=user.id,
        incident_id=incident.id,
        event_id=None,
        alert_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        status=AlertStatusEnum.pending,
        message="Alert for audit failure tests",
    )
    ctx.db.add(alert)
    ctx.db.commit()
    ctx.db.refresh(alert)

    return user, device, incident, alert


def test_login_failed_generates_audit_log(ctx: ClientAndDB) -> None:
    before = _count_audit(ctx.db, "auth.login.failed")

    response = ctx.client.post("/auth/login", json={"username": "admin", "password": "wrong-password"})

    assert response.status_code == 401
    after = _count_audit(ctx.db, "auth.login.failed")
    assert after == before + 1

    log = _latest_audit(ctx.db, "auth.login.failed")
    assert log is not None
    assert log.actor_type == "frontend_user"
    assert log.actor_identifier == "admin"
    assert log.target_type == "frontend_auth"
    assert log.target_identifier == "admin"
    assert isinstance(log.metadata_json, dict)
    assert log.metadata_json.get("reason") == "invalid_credentials"


def test_login_success_generates_audit_log(ctx: ClientAndDB) -> None:
    before = _count_audit(ctx.db, "auth.login.success")

    response = ctx.client.post("/auth/login", json={"username": "admin", "password": "admin123"})

    assert response.status_code == 200
    after = _count_audit(ctx.db, "auth.login.success")
    assert after == before + 1

    log = _latest_audit(ctx.db, "auth.login.success")
    assert log is not None
    assert log.actor_type == "frontend_user"
    assert log.actor_identifier == "admin"
    assert log.target_type == "frontend_auth"
    assert log.target_identifier == "admin"


def test_create_device_generates_audit_log(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)

    user_response = ctx.client.post(
        "/users",
        json={"full_name": "Audit User", "birth_date": None, "notes": None},
        headers=headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    before = _count_audit(ctx.db, "device.create")
    device_code = "audit-device-create-001"
    response = ctx.client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "Audit Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 201

    after = _count_audit(ctx.db, "device.create")
    assert after == before + 1

    log = _latest_audit(ctx.db, "device.create")
    assert log is not None
    assert log.actor_type == "frontend_user"
    assert log.actor_identifier == "admin"
    assert log.target_type == "device"
    assert log.target_identifier == device_code


def test_rotate_token_generates_audit_log(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)

    user_response = ctx.client.post(
        "/users",
        json={"full_name": "Audit Rotate User", "birth_date": None, "notes": None},
        headers=headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    device_code = "audit-device-rotate-001"
    provision_response = ctx.client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "Audit Rotate Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=headers,
    )
    assert provision_response.status_code == 201

    before = _count_audit(ctx.db, "device.rotate_token")
    rotate_response = ctx.client.post(f"/devices/{device_code}/rotate-token", headers=headers)
    assert rotate_response.status_code == 200

    after = _count_audit(ctx.db, "device.rotate_token")
    assert after == before + 1

    log = _latest_audit(ctx.db, "device.rotate_token")
    assert log is not None
    assert log.actor_type == "frontend_user"
    assert log.actor_identifier == "admin"
    assert log.target_type == "device"
    assert log.target_identifier == device_code


def test_login_failed_keeps_working_when_audit_fails(ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import audit_service

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit_service, "record_audit_event", _raise_audit_error)

    response = ctx.client.post("/auth/login", json={"username": "admin", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_success_keeps_working_when_audit_fails(ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import audit_service

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit_service, "record_audit_event", _raise_audit_error)

    response = ctx.client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_create_device_fails_when_required_audit_fails(
    ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import devices as devices_api

    headers = _frontend_headers(ctx.client)
    user_response = ctx.client.post(
        "/users",
        json={"full_name": "Required Audit User", "birth_date": None, "notes": None},
        headers=headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(devices_api, "record_audit_event", _raise_audit_error)

    device_code = "audit-required-device-create-001"
    response = ctx.client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "Required Audit Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["message"] == "Action could not be completed because required audit logging failed"
    assert response.json()["code"] == 503
    assert _get_device_by_code(ctx.db, device_code) is None


def test_rotate_token_fails_when_required_audit_fails(
    ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import devices as devices_api

    headers = _frontend_headers(ctx.client)
    user_response = ctx.client.post(
        "/users",
        json={"full_name": "Required Audit Rotate User", "birth_date": None, "notes": None},
        headers=headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    device_code = "audit-required-device-rotate-001"
    provision_response = ctx.client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "Required Audit Rotate Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=headers,
    )
    assert provision_response.status_code == 201

    device_before = _get_device_by_code(ctx.db, device_code)
    assert device_before is not None
    token_hash_before = device_before.device_token_hash
    rotated_at_before = device_before.token_rotated_at

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(devices_api, "record_audit_event", _raise_audit_error)

    rotate_response = ctx.client.post(f"/devices/{device_code}/rotate-token", headers=headers)
    assert rotate_response.status_code == 503
    assert rotate_response.json()["message"] == "Action could not be completed because required audit logging failed"
    assert rotate_response.json()["code"] == 503

    device_after = _get_device_by_code(ctx.db, device_code)
    assert device_after is not None
    assert device_after.device_token_hash == token_hash_before
    assert device_after.token_rotated_at == rotated_at_before


def test_incident_close_fails_when_required_audit_fails(
    ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import incidents as incidents_api

    headers = _frontend_headers(ctx.client)
    _, _, incident, _ = _seed_user_device_incident_alert(ctx)

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(incidents_api, "record_audit_event", _raise_audit_error)

    response = ctx.client.patch(f"/incidents/{incident.id}/close", headers=headers)
    assert response.status_code == 503
    assert response.json()["message"] == "Action could not be completed because required audit logging failed"
    assert response.json()["code"] == 503

    incident_after = ctx.db.get(Incident, incident.id)
    assert incident_after is not None
    assert incident_after.status == IncidentStatusEnum.open
    assert incident_after.closed_at is None


def test_alert_acknowledge_fails_when_required_audit_fails(
    ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import alerts as alerts_api

    headers = _frontend_headers(ctx.client)
    _, _, _, alert = _seed_user_device_incident_alert(ctx)

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(alerts_api, "record_audit_event", _raise_audit_error)

    response = ctx.client.patch(f"/alerts/{alert.id}/acknowledge", headers=headers)
    assert response.status_code == 503
    assert response.json()["message"] == "Action could not be completed because required audit logging failed"
    assert response.json()["code"] == 503

    alert_after = ctx.db.get(Alert, alert.id)
    assert alert_after is not None
    assert alert_after.status == AlertStatusEnum.pending


def test_alert_resolve_fails_when_required_audit_fails(
    ctx: ClientAndDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import alerts as alerts_api

    headers = _frontend_headers(ctx.client)
    _, _, _, alert = _seed_user_device_incident_alert(ctx)
    alert.status = AlertStatusEnum.acknowledged
    ctx.db.add(alert)
    ctx.db.commit()
    ctx.db.refresh(alert)

    def _raise_audit_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(alerts_api, "record_audit_event", _raise_audit_error)

    response = ctx.client.patch(f"/alerts/{alert.id}/resolve", headers=headers)
    assert response.status_code == 503
    assert response.json()["message"] == "Action could not be completed because required audit logging failed"
    assert response.json()["code"] == 503

    alert_after = ctx.db.get(Alert, alert.id)
    assert alert_after is not None
    assert alert_after.status == AlertStatusEnum.acknowledged
