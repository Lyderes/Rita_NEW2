from __future__ import annotations

from collections.abc import Generator
from typing import NamedTuple

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.db.session import get_db
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.main import app
from app.models.alert import Alert
from app.models.device import Device
from app.models.incident import Incident
from app.models.user import User
from app.services.state_transition_service import (
    InvalidStateTransitionError,
    VALID_ALERT_TRANSITIONS,
    VALID_INCIDENT_TRANSITIONS,
    apply_incident_transition,
    validate_alert_transition,
    validate_incident_transition,
)


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


def _seed_open_incident(ctx: ClientAndDB) -> Incident:
    user = User(full_name="Transition User", birth_date=None, notes=None)
    ctx.db.add(user)
    ctx.db.commit()
    ctx.db.refresh(user)

    device = Device(
        user_id=user.id,
        device_code="transition-device-001",
        device_token_hash=None,
        device_name="Transition Device",
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
        summary="Transition incident",
    )
    ctx.db.add(incident)
    ctx.db.commit()
    ctx.db.refresh(incident)
    return incident


def _seed_alert(ctx: ClientAndDB, *, status: AlertStatusEnum = AlertStatusEnum.pending) -> Alert:
    incident = _seed_open_incident(ctx)
    alert = Alert(
        user_id=incident.user_id,
        incident_id=incident.id,
        event_id=None,
        alert_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        status=status,
        message="Transition alert",
    )
    ctx.db.add(alert)
    ctx.db.commit()
    ctx.db.refresh(alert)
    return alert


def test_incident_close_valid_transition(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)
    incident = _seed_open_incident(ctx)

    response = ctx.client.patch(f"/incidents/{incident.id}/close", headers=headers)

    assert response.status_code == 200
    ctx.db.expire_all()
    incident_after = ctx.db.get(Incident, incident.id)
    assert incident_after is not None
    assert incident_after.status == IncidentStatusEnum.closed
    assert incident_after.closed_at is not None


def test_incident_close_is_idempotent_when_already_closed(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)
    incident = _seed_open_incident(ctx)
    incident.status = IncidentStatusEnum.closed
    ctx.db.add(incident)
    ctx.db.commit()
    ctx.db.refresh(incident)
    closed_at_before = incident.closed_at

    response = ctx.client.patch(f"/incidents/{incident.id}/close", headers=headers)

    assert response.status_code == 200
    ctx.db.expire_all()
    incident_after = ctx.db.get(Incident, incident.id)
    assert incident_after is not None
    assert incident_after.status == IncidentStatusEnum.closed
    assert incident_after.closed_at == closed_at_before


def test_alert_acknowledge_valid_transition(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)
    alert = _seed_alert(ctx)

    response = ctx.client.patch(f"/alerts/{alert.id}/acknowledge", headers=headers)

    assert response.status_code == 200
    ctx.db.expire_all()
    alert_after = ctx.db.get(Alert, alert.id)
    assert alert_after is not None
    assert alert_after.status == AlertStatusEnum.acknowledged


def test_alert_resolve_valid_transition_from_acknowledged(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)
    alert = _seed_alert(ctx, status=AlertStatusEnum.acknowledged)

    response = ctx.client.patch(f"/alerts/{alert.id}/resolve", headers=headers)

    assert response.status_code == 200
    ctx.db.expire_all()
    alert_after = ctx.db.get(Alert, alert.id)
    assert alert_after is not None
    assert alert_after.status == AlertStatusEnum.resolved


def test_alert_acknowledge_invalid_transition_returns_409(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)
    alert = _seed_alert(ctx, status=AlertStatusEnum.resolved)

    response = ctx.client.patch(f"/alerts/{alert.id}/acknowledge", headers=headers)

    assert response.status_code == 409
    body = response.json()
    detail_or_message = body.get("detail") or body.get("message")
    assert detail_or_message == "Invalid state transition: resolved → acknowledged"
    ctx.db.expire_all()
    alert_after = ctx.db.get(Alert, alert.id)
    assert alert_after is not None
    assert alert_after.status == AlertStatusEnum.resolved


def test_alert_acknowledge_is_idempotent_when_already_acknowledged(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)
    alert = _seed_alert(ctx, status=AlertStatusEnum.acknowledged)

    response = ctx.client.patch(f"/alerts/{alert.id}/acknowledge", headers=headers)

    assert response.status_code == 200
    ctx.db.expire_all()
    alert_after = ctx.db.get(Alert, alert.id)
    assert alert_after is not None
    assert alert_after.status == AlertStatusEnum.acknowledged


def test_alert_resolve_is_idempotent_when_already_resolved(ctx: ClientAndDB) -> None:
    headers = _frontend_headers(ctx.client)
    alert = _seed_alert(ctx, status=AlertStatusEnum.resolved)

    response = ctx.client.patch(f"/alerts/{alert.id}/resolve", headers=headers)

    assert response.status_code == 200
    ctx.db.expire_all()
    alert_after = ctx.db.get(Alert, alert.id)
    assert alert_after is not None
    assert alert_after.status == AlertStatusEnum.resolved


def test_transition_tables_are_explicit() -> None:
    assert VALID_INCIDENT_TRANSITIONS[IncidentStatusEnum.open] == frozenset(
        {IncidentStatusEnum.acknowledged, IncidentStatusEnum.closed}
    )
    assert VALID_ALERT_TRANSITIONS[AlertStatusEnum.pending] == frozenset(
        {AlertStatusEnum.acknowledged, AlertStatusEnum.resolved}
    )


def test_incident_transition_open_to_acknowledged_is_allowed(ctx: ClientAndDB) -> None:
    incident = _seed_open_incident(ctx)

    changed = apply_incident_transition(incident, IncidentStatusEnum.acknowledged)

    assert changed is True
    assert incident.status == IncidentStatusEnum.acknowledged


def test_incident_transition_acknowledged_to_resolved_is_allowed(ctx: ClientAndDB) -> None:
    incident = _seed_open_incident(ctx)
    incident.status = IncidentStatusEnum.acknowledged

    changed = apply_incident_transition(incident, IncidentStatusEnum.resolved)

    assert changed is True
    assert incident.status == IncidentStatusEnum.resolved


def test_incident_transition_resolved_to_closed_is_allowed(ctx: ClientAndDB) -> None:
    incident = _seed_open_incident(ctx)
    incident.status = IncidentStatusEnum.resolved

    changed = apply_incident_transition(incident, IncidentStatusEnum.closed)

    assert changed is True
    assert incident.status == IncidentStatusEnum.closed


def test_validate_incident_transition_rejects_invalid_transition() -> None:
    with pytest.raises(InvalidStateTransitionError, match="closed → open"):
        validate_incident_transition(IncidentStatusEnum.closed, IncidentStatusEnum.open)


def test_validate_incident_transition_rejects_closed_to_resolved() -> None:
    with pytest.raises(InvalidStateTransitionError, match="closed → resolved"):
        validate_incident_transition(IncidentStatusEnum.closed, IncidentStatusEnum.resolved)


def test_validate_alert_transition_rejects_invalid_transition() -> None:
    with pytest.raises(InvalidStateTransitionError, match="resolved → acknowledged"):
        validate_alert_transition(AlertStatusEnum.resolved, AlertStatusEnum.acknowledged)