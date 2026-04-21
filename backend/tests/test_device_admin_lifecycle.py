from __future__ import annotations

from collections.abc import Generator
from typing import NamedTuple
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
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_user_and_device(client: TestClient, *, device_code: str) -> tuple[int, str, str]:
    frontend_headers = _frontend_headers(client)
    user_response = client.post(
        "/users",
        json={"full_name": "Admin Lifecycle User", "birth_date": None, "notes": None},
        headers=frontend_headers,
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    device_response = client.post(
        "/devices",
        json={
            "user_id": user_id,
            "device_code": device_code,
            "device_name": "Admin Lifecycle Device",
            "location_name": "Salon",
            "is_active": True,
        },
        headers=frontend_headers,
    )
    assert device_response.status_code == 201
    payload = device_response.json()
    return user_id, payload["device_code"], payload["device_token"]


def _event_payload(device_code: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "trace_id": str(uuid4()),
        "device_code": device_code,
        "event_type": "fall",
        "severity": "high",
        "source": "rita-edge",
    }


def test_active_device_can_send_event(ctx: ClientAndDB) -> None:
    _, device_code, device_token = _create_user_and_device(ctx.client, device_code="admin-active-001")

    response = ctx.client.post(
        "/events",
        json=_event_payload(device_code),
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 201


def test_suspended_device_cannot_send_event(ctx: ClientAndDB) -> None:
    _, device_code, device_token = _create_user_and_device(ctx.client, device_code="admin-suspended-event-001")

    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    device.admin_status = DeviceAdminStatusEnum.suspended
    device.admin_status_reason = "manual lock"
    ctx.db.add(device)
    ctx.db.commit()

    response = ctx.client.post(
        "/events",
        json=_event_payload(device_code),
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 403
    detail = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail, str)
    assert "not allowed to operate" in detail.lower()


def test_suspended_device_cannot_send_heartbeat(ctx: ClientAndDB) -> None:
    _, device_code, device_token = _create_user_and_device(ctx.client, device_code="admin-suspended-heartbeat-001")

    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    device.admin_status = DeviceAdminStatusEnum.suspended
    device.admin_status_reason = "manual lock"
    ctx.db.add(device)
    ctx.db.commit()

    response = ctx.client.post(
        f"/devices/{device_code}/heartbeat",
        headers={"X-Device-Token": device_token},
    )

    assert response.status_code == 403
    detail = response.json().get("detail") or response.json().get("message")
    assert isinstance(detail, str)
    assert "not allowed to operate" in detail.lower()


def test_reactivated_device_works_again(ctx: ClientAndDB) -> None:
    _, device_code, device_token = _create_user_and_device(ctx.client, device_code="admin-reactivated-001")

    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    device.admin_status = DeviceAdminStatusEnum.suspended
    device.admin_status_reason = "manual lock"
    ctx.db.add(device)
    ctx.db.commit()

    blocked = ctx.client.post(
        "/events",
        json=_event_payload(device_code),
        headers={"X-Device-Token": device_token},
    )
    assert blocked.status_code == 403

    device = ctx.db.scalar(select(Device).where(Device.device_code == device_code))
    assert device is not None
    device.admin_status = DeviceAdminStatusEnum.active
    device.admin_status_reason = "reactivated"
    ctx.db.add(device)
    ctx.db.commit()

    response = ctx.client.post(
        "/events",
        json=_event_payload(device_code),
        headers={"X-Device-Token": device_token},
    )
    assert response.status_code == 201