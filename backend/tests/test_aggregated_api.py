from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import require_frontend_auth
from app.db.base import Base, register_models
from app.db.session import get_db
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.main import app
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User


@pytest.fixture()
def client_and_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
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
    app.dependency_overrides[require_frontend_auth] = lambda: "test-frontend"
    try:
        with TestClient(app) as client:
            yield client, session_local
    finally:
        app.dependency_overrides.clear()


def _seed_aggregated_data(session_local: sessionmaker[Session]) -> dict[str, int]:
    now = datetime.now(UTC)
    db = session_local()
    try:
        user_1 = User(full_name="Ana")
        user_2 = User(full_name="Beto")
        db.add_all([user_1, user_2])
        db.flush()

        device_online = Device(
            user_id=user_1.id,
            device_code="dev-online",
            device_name="Pulsera Ana",
            is_active=True,
            last_seen_at=now - timedelta(minutes=2),
        )
        device_stale = Device(
            user_id=user_1.id,
            device_code="dev-stale",
            device_name="Colgante Ana",
            is_active=True,
            last_seen_at=now - timedelta(minutes=10),
        )
        device_offline = Device(
            user_id=user_2.id,
            device_code="dev-offline",
            device_name="Pulsera Beto",
            is_active=False,
            last_seen_at=None,
        )
        db.add_all([device_online, device_stale, device_offline])
        db.flush()

        older_event = Event(
            trace_id=str(uuid4()),
            user_id=user_1.id,
            device_id=device_online.id,
            event_type=EventTypeEnum.checkin,
            severity=SeverityEnum.low,
            source="rita-edge",
            user_text="estoy bien",
            rita_text="me alegra",
            payload_json={"origin": "test"},
            created_at=now - timedelta(minutes=15),
        )
        latest_event = Event(
            trace_id=str(uuid4()),
            user_id=user_1.id,
            device_id=device_stale.id,
            event_type=EventTypeEnum.fall,
            severity=SeverityEnum.high,
            source="rita-edge",
            user_text="me he caido",
            rita_text="te ayudo",
            payload_json={"origin": "test"},
            created_at=now - timedelta(minutes=1),
        )
        db.add_all([older_event, latest_event])
        db.flush()

        open_incident = Incident(
            user_id=user_1.id,
            device_id=device_stale.id,
            event_id=latest_event.id,
            incident_type=EventTypeEnum.fall,
            status=IncidentStatusEnum.open,
            severity=SeverityEnum.high,
            summary="Caida detectada",
            opened_at=now - timedelta(minutes=1),
        )
        closed_incident = Incident(
            user_id=user_2.id,
            device_id=device_offline.id,
            event_id=None,
            incident_type=EventTypeEnum.emergency,
            status=IncidentStatusEnum.closed,
            severity=SeverityEnum.medium,
            summary="Incidente cerrado",
            opened_at=now - timedelta(days=1),
            closed_at=now - timedelta(hours=20),
        )
        db.add_all([open_incident, closed_incident])
        db.flush()

        pending_alert = Alert(
            user_id=user_1.id,
            incident_id=open_incident.id,
            event_id=latest_event.id,
            alert_type=EventTypeEnum.fall,
            severity=SeverityEnum.high,
            status=AlertStatusEnum.pending,
            message="Alerta pendiente",
            created_at=now - timedelta(minutes=1),
        )
        acknowledged_alert_same_user = Alert(
            user_id=user_1.id,
            incident_id=open_incident.id,
            event_id=older_event.id,
            alert_type=EventTypeEnum.checkin,
            severity=SeverityEnum.low,
            status=AlertStatusEnum.acknowledged,
            message="Alerta ya vista",
            created_at=now - timedelta(minutes=12),
        )
        acknowledged_alert = Alert(
            user_id=user_2.id,
            incident_id=closed_incident.id,
            event_id=None,
            alert_type=EventTypeEnum.emergency,
            severity=SeverityEnum.medium,
            status=AlertStatusEnum.acknowledged,
            message="Alerta gestionada",
            created_at=now - timedelta(hours=12),
        )
        db.add_all([pending_alert, acknowledged_alert_same_user, acknowledged_alert])
        db.commit()

        return {"user_1_id": user_1.id, "user_2_id": user_2.id}
    finally:
        db.close()


def test_get_dashboard_returns_aggregated_summary(client_and_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_local = client_and_session
    _seed_aggregated_data(session_local)

    response = client.get("/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["users_total"] == 2
    assert payload["devices_total"] == 3
    assert payload["devices_active"] == 2
    assert payload["devices_online"] == 1
    assert payload["incidents_open"] == 1
    assert payload["alerts_pending"] == 1
    assert payload["last_event_type"] == "fall"
    assert payload["last_event_at"] is not None


def test_get_dashboard_returns_empty_summary_when_there_is_no_data(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "users_total": 0,
        "devices_total": 0,
        "devices_active": 0,
        "devices_online": 0,
        "incidents_open": 0,
        "alerts_pending": 0,
        "last_event_at": None,
        "last_event_type": None,
    }


def test_get_devices_status_classifies_online_stale_offline(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    _seed_aggregated_data(session_local)

    response = client.get("/devices/status")

    assert response.status_code == 200
    payload = {item["device_code"]: item for item in response.json()}
    assert payload["dev-online"]["connection_status"] == "online"
    assert payload["dev-stale"]["connection_status"] == "stale"
    assert payload["dev-offline"]["connection_status"] == "offline"


def test_get_devices_status_does_not_expose_token_fields(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    _seed_aggregated_data(session_local)

    response = client.get("/devices/status")

    assert response.status_code == 200
    for item in response.json():
        assert "device_token" not in item
        assert "device_token_hash" not in item


def test_get_devices_status_returns_empty_list_when_there_are_no_devices(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session

    response = client.get("/devices/status")

    assert response.status_code == 200
    assert response.json() == []


def test_get_user_overview_returns_aggregated_user_view(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    ids = _seed_aggregated_data(session_local)

    response = client.get(f"/users/{ids['user_1_id']}/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == ids["user_1_id"]
    assert payload["user_name"] == "Ana"
    assert payload["current_status"] == "critical"
    assert payload["pending_alerts"] == 1
    assert payload["open_incident"]["status"] == "open"
    assert payload["open_incident"]["severity"] == "high"
    assert payload["last_event"]["event_type"] == "fall"
    assert payload["last_event"]["severity"] == "high"
    assert len(payload["devices"]) == 2
    assert len(payload["recent_events"]) == 2
    assert len(payload["recent_alerts"]) == 2
    assert payload["recent_events"][0]["event_type"] == "fall"
    assert payload["recent_events"][1]["event_type"] == "checkin"
    assert payload["recent_alerts"][0]["status"] == "pending"
    assert payload["recent_alerts"][1]["status"] == "acknowledged"
    assert payload["recent_alerts"][0]["created_at"] >= payload["recent_alerts"][1]["created_at"]
    assert payload["devices"][0]["connection_status"] in {"online", "stale", "offline"}


def test_get_user_overview_devices_do_not_expose_token_fields(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    ids = _seed_aggregated_data(session_local)

    response = client.get(f"/users/{ids['user_1_id']}/overview")

    assert response.status_code == 200
    for device in response.json()["devices"]:
        assert "device_token" not in device
        assert "device_token_hash" not in device


def test_get_user_overview_returns_empty_collections_and_nulls_for_user_without_activity(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    db = session_local()
    try:
        user = User(full_name="No Activity")
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    response = client.get(f"/users/{user_id}/overview")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": user_id,
        "user_name": "No Activity",
        "current_status": "ok",
        "last_event": None,
        "open_incident": None,
        "pending_alerts": 0,
        "devices": [],
        "recent_events": [],
        "recent_alerts": [],
    }


def test_aggregated_payloads_keep_enums_as_plain_strings(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    ids = _seed_aggregated_data(session_local)

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["last_event_type"] == "fall"
    assert isinstance(dashboard_response.json()["last_event_type"], str)

    overview_response = client.get(f"/users/{ids['user_1_id']}/overview")
    assert overview_response.status_code == 200
    payload = overview_response.json()
    assert payload["last_event"]["event_type"] == "fall"
    assert isinstance(payload["last_event"]["event_type"], str)
    assert payload["open_incident"]["status"] == "open"
    assert isinstance(payload["open_incident"]["status"], str)


def test_get_user_status_uses_warning_range_when_warning_alert_is_active(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    ids = _seed_aggregated_data(session_local)

    response = client.get(f"/users/{ids['user_1_id']}/status")

    assert response.status_code == 200
    payload = response.json()
    assert 40 <= payload["wellbeing_score"] <= 70
    assert payload["wellbeing_state"] == "atencion"


def test_get_user_status_critical_pending_alert_dominates_score(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    ids = _seed_aggregated_data(session_local)

    db = session_local()
    try:
        open_incident = db.query(Incident).filter(Incident.user_id == ids["user_1_id"]).first()
        assert open_incident is not None
        critical_alert = Alert(
            user_id=ids["user_1_id"],
            incident_id=open_incident.id,
            event_id=None,
            alert_type=EventTypeEnum.emergency,
            severity=SeverityEnum.critical,
            status=AlertStatusEnum.pending,
            message="Alerta critica activa",
        )
        db.add(critical_alert)
        db.commit()
    finally:
        db.close()

    response = client.get(f"/users/{ids['user_1_id']}/status")

    assert response.status_code == 200
    payload = response.json()
    assert 0 <= payload["wellbeing_score"] <= 25
    assert payload["wellbeing_state"] == "critico"


def test_get_user_status_critical_acknowledged_alert_still_dominates_score(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session

    db = session_local()
    try:
        user = User(full_name="Critical Acknowledged")
        db.add(user)
        db.flush()

        device = Device(
            user_id=user.id,
            device_code="dev-critical-ack",
            device_name="Pulsera Critical Ack",
            is_active=True,
        )
        db.add(device)
        db.flush()

        incident = Incident(
            user_id=user.id,
            device_id=device.id,
            event_id=None,
            incident_type=EventTypeEnum.emergency,
            status=IncidentStatusEnum.closed,
            severity=SeverityEnum.critical,
            summary="Incidente cerrado",
        )
        db.add(incident)
        db.flush()

        alert = Alert(
            user_id=user.id,
            incident_id=incident.id,
            event_id=None,
            alert_type=EventTypeEnum.emergency,
            severity=SeverityEnum.critical,
            status=AlertStatusEnum.acknowledged,
            message="Alerta critica en curso",
        )
        db.add(alert)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    response = client.get(f"/users/{user_id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert 0 <= payload["wellbeing_score"] <= 25
    assert payload["wellbeing_state"] == "critico"


def test_get_user_status_resolved_critical_alert_does_not_affect_score(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session

    db = session_local()
    try:
        user = User(full_name="Resolved Critical")
        db.add(user)
        db.flush()

        device = Device(
            user_id=user.id,
            device_code="dev-resolved-critical",
            device_name="Pulsera Resolved",
            is_active=True,
        )
        db.add(device)
        db.flush()

        incident = Incident(
            user_id=user.id,
            device_id=device.id,
            event_id=None,
            incident_type=EventTypeEnum.emergency,
            status=IncidentStatusEnum.closed,
            severity=SeverityEnum.critical,
            summary="Incidente cerrado",
        )
        db.add(incident)
        db.flush()

        resolved_alert = Alert(
            user_id=user.id,
            incident_id=incident.id,
            event_id=None,
            alert_type=EventTypeEnum.emergency,
            severity=SeverityEnum.critical,
            status=AlertStatusEnum.resolved,
            message="Alerta critica resuelta",
        )
        db.add(resolved_alert)

        event = Event(
            trace_id=str(uuid4()),
            user_id=user.id,
            device_id=device.id,
            event_type=EventTypeEnum.checkin,
            severity=SeverityEnum.low,
            source="rita-edge",
            user_text="estoy bien",
            rita_text="ok",
            payload_json={"origin": "test"},
        )
        db.add(event)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    response = client.get(f"/users/{user_id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["wellbeing_score"] == 100
    assert payload["wellbeing_state"] == "estable"


def test_get_user_status_base_scoring_without_active_severe_alerts(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = client_and_session
    db = session_local()
    try:
        user = User(full_name="Base Score")
        db.add(user)
        db.flush()

        device = Device(
            user_id=user.id,
            device_code="dev-base-score",
            device_name="Pulsera Base",
            is_active=True,
        )
        db.add(device)
        db.flush()

        event = Event(
            trace_id=str(uuid4()),
            user_id=user.id,
            device_id=device.id,
            event_type=EventTypeEnum.checkin,
            severity=SeverityEnum.low,
            source="rita-edge",
            user_text="todo bien",
            rita_text="ok",
            payload_json={"origin": "test"},
        )
        db.add(event)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    response = client.get(f"/users/{user_id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert 0 <= payload["wellbeing_score"] <= 100
    assert payload["wellbeing_score"] == 100
    assert payload["wellbeing_state"] == "estable"


def test_get_user_overview_returns_404_for_missing_user(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session

    response = client.get("/users/999999/overview")

    assert response.status_code == 404
    assert response.json()["message"] == "User not found"
    assert response.json()["error"] == "not_found"