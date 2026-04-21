from __future__ import annotations

from datetime import UTC, datetime, timedelta
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.alerts import get_alert, list_alerts
from app.api.events import list_events
from app.api.incidents import get_incident, list_incidents
from app.api.users import get_user_timeline
from app.db.base import Base, register_models
from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


def _seed_user_device(db: Session, *, name: str, device_code: str) -> tuple[User, Device]:
    user = User(full_name=name)
    db.add(user)
    db.flush()

    device = Device(
        user_id=user.id,
        device_code=device_code,
        device_name=f"{name} device",
        is_active=True,
    )
    db.add(device)
    db.flush()
    return user, device


def _seed_event_incident_alert(
    db: Session,
    *,
    user_id: int,
    device_id: int,
    event_type: EventTypeEnum,
    severity: SeverityEnum,
    incident_status: IncidentStatusEnum,
    alert_status: AlertStatusEnum,
    stamp: datetime,
) -> tuple[Event, Incident, Alert]:
    event = Event(
        trace_id=str(uuid4()),
        user_id=user_id,
        device_id=device_id,
        event_type=event_type,
        severity=severity,
        source="rita-edge",
        user_text=f"user {event_type}",
        rita_text="rita",
        payload_json={"origin": "test"},
        created_at=stamp,
    )
    db.add(event)
    db.flush()

    incident = Incident(
        user_id=user_id,
        device_id=device_id,
        event_id=event.id,
        incident_type=event_type,
        status=incident_status,
        severity=severity,
        summary=f"incident {event_type}",
        opened_at=stamp,
    )
    db.add(incident)
    db.flush()

    alert = Alert(
        user_id=user_id,
        incident_id=incident.id,
        event_id=event.id,
        alert_type=event_type,
        severity=severity,
        status=alert_status,
        message=f"alert {event_type}",
        created_at=stamp,
    )
    db.add(alert)
    db.flush()

    return event, incident, alert


def test_get_incident_detail_and_404(db: Session) -> None:
    user, device = _seed_user_device(db, name="Ana", device_code="dev-a")
    _, incident, _ = _seed_event_incident_alert(
        db,
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=datetime.now(UTC),
    )
    db.commit()

    found = get_incident(incident_id=incident.id, db=db)
    assert found.id == incident.id
    assert found.incident_type == EventTypeEnum.fall

    with pytest.raises(HTTPException) as exc:
        get_incident(incident_id=999999, db=db)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Incident not found"


def test_get_alert_detail_and_404(db: Session) -> None:
    user, device = _seed_user_device(db, name="Beto", device_code="dev-b")
    _, _, alert = _seed_event_incident_alert(
        db,
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.emergency,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=datetime.now(UTC),
    )
    db.commit()

    found = get_alert(alert_id=alert.id, db=db)
    assert found.id == alert.id
    assert found.alert_type == EventTypeEnum.emergency

    with pytest.raises(HTTPException) as exc:
        get_alert(alert_id=999999, db=db)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Alert not found"


def test_incidents_filters_limit_and_order(db: Session) -> None:
    now = datetime.now(UTC)
    user_1, device_1 = _seed_user_device(db, name="Carla", device_code="dev-c")
    user_2, device_2 = _seed_user_device(db, name="Dani", device_code="dev-d")

    _seed_event_incident_alert(
        db,
        user_id=user_1.id,
        device_id=device_1.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=10),
    )
    _, target_incident, _ = _seed_event_incident_alert(
        db,
        user_id=user_1.id,
        device_id=device_1.id,
        event_type=EventTypeEnum.emergency,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=1),
    )
    _seed_event_incident_alert(
        db,
        user_id=user_2.id,
        device_id=device_2.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.medium,
        incident_status=IncidentStatusEnum.closed,
        alert_status=AlertStatusEnum.acknowledged,
        stamp=now - timedelta(minutes=5),
    )
    db.commit()

    page = list_incidents(
        user_id=user_1.id,
        device_id=device_1.id,
        incident_type=EventTypeEnum.emergency,
        status=IncidentStatusEnum.open,
        severity=SeverityEnum.high,
        date_from=now - timedelta(minutes=6),
        date_to=now,
        order="desc",
        limit=2,
        offset=0,
        db=db,
    )
    items = page.items
    assert page.total == 1
    assert page.limit == 2
    assert page.offset == 0
    assert len(items) == 1
    assert items[0].id == target_incident.id


def test_alerts_filters_limit_and_order(db: Session) -> None:
    now = datetime.now(UTC)
    user_1, device_1 = _seed_user_device(db, name="Elena", device_code="dev-e")
    user_2, device_2 = _seed_user_device(db, name="Fede", device_code="dev-f")

    _seed_event_incident_alert(
        db,
        user_id=user_1.id,
        device_id=device_1.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=20),
    )
    _, _, target_alert = _seed_event_incident_alert(
        db,
        user_id=user_1.id,
        device_id=device_1.id,
        event_type=EventTypeEnum.emergency,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=2),
    )
    _seed_event_incident_alert(
        db,
        user_id=user_2.id,
        device_id=device_2.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.medium,
        incident_status=IncidentStatusEnum.closed,
        alert_status=AlertStatusEnum.acknowledged,
        stamp=now - timedelta(minutes=8),
    )
    db.commit()

    page = list_alerts(
        user_id=user_1.id,
        alert_type=EventTypeEnum.emergency,
        status=AlertStatusEnum.pending,
        severity=SeverityEnum.high,
        date_from=now - timedelta(minutes=4),
        date_to=now,
        order="desc",
        limit=2,
        offset=0,
        db=db,
    )
    items = page.items
    assert page.total == 1
    assert page.limit == 2
    assert page.offset == 0
    assert len(items) == 1
    assert items[0].id == target_alert.id


def test_events_filters_limit_and_order(db: Session) -> None:
    now = datetime.now(UTC)
    user_1, device_1 = _seed_user_device(db, name="Gina", device_code="dev-g")
    user_2, device_2 = _seed_user_device(db, name="Hugo", device_code="dev-h")

    _seed_event_incident_alert(
        db,
        user_id=user_1.id,
        device_id=device_1.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.closed,
        alert_status=AlertStatusEnum.acknowledged,
        stamp=now - timedelta(minutes=12),
    )
    target_event, _, _ = _seed_event_incident_alert(
        db,
        user_id=user_1.id,
        device_id=device_1.id,
        event_type=EventTypeEnum.emergency,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=3),
    )
    _seed_event_incident_alert(
        db,
        user_id=user_2.id,
        device_id=device_2.id,
        event_type=EventTypeEnum.checkin,
        severity=SeverityEnum.low,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=1),
    )
    db.commit()

    page = list_events(
        user_id=user_1.id,
        device_id=device_1.id,
        event_type=EventTypeEnum.emergency,
        severity=SeverityEnum.high,
        date_from=now - timedelta(minutes=5),
        date_to=now,
        order="desc",
        limit=2,
        offset=0,
        db=db,
    )
    items = page.items
    assert page.total == 1
    assert page.limit == 2
    assert page.offset == 0
    assert len(items) == 1
    assert items[0].id == target_event.id

    ordered_page = list_events(
        user_id=user_1.id,
        device_id=None,
        event_type=None,
        severity=SeverityEnum.high,
        date_from=None,
        date_to=None,
        order="desc",
        limit=2,
        offset=0,
        db=db,
    )
    assert len(ordered_page.items) == 2
    assert ordered_page.items[0].created_at >= ordered_page.items[1].created_at


def test_events_pagination_offset_and_total(db: Session) -> None:
    now = datetime.now(UTC)
    user, device = _seed_user_device(db, name="Lia", device_code="dev-l")
    for idx in range(4):
        _seed_event_incident_alert(
            db,
            user_id=user.id,
            device_id=device.id,
            event_type=EventTypeEnum.fall,
            severity=SeverityEnum.high,
            incident_status=IncidentStatusEnum.open,
            alert_status=AlertStatusEnum.pending,
            stamp=now - timedelta(minutes=idx),
        )
    db.commit()

    page = list_events(
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        date_from=None,
        date_to=None,
        order="desc",
        limit=2,
        offset=1,
        db=db,
    )

    assert page.total == 4
    assert page.limit == 2
    assert page.offset == 1
    assert len(page.items) == 2


def test_alerts_order_asc_returns_oldest_first(db: Session) -> None:
    now = datetime.now(UTC)
    user, device = _seed_user_device(db, name="Marta", device_code="dev-m")
    _seed_event_incident_alert(
        db,
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=4),
    )
    _seed_event_incident_alert(
        db,
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.emergency,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=now - timedelta(minutes=1),
    )
    db.commit()

    page = list_alerts(
        user_id=user.id,
        alert_type=None,
        status=AlertStatusEnum.pending,
        severity=SeverityEnum.high,
        date_from=None,
        date_to=None,
        order="asc",
        limit=10,
        offset=0,
        db=db,
    )

    assert len(page.items) == 2
    assert page.items[0].created_at <= page.items[1].created_at


def test_events_date_from_and_date_to_are_inclusive(db: Session) -> None:
    """Eventos creados EXACTAMENTE en date_from o date_to deben incluirse (>= / <=)."""
    exact = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    user, device = _seed_user_device(db, name="Noa", device_code="dev-n")

    # evento exactamente en el borde inferior
    ev_at_from, _, _ = _seed_event_incident_alert(
        db,
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=exact,
    )
    # evento exactamente en el borde superior
    ev_at_to, _, _ = _seed_event_incident_alert(
        db,
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=exact + timedelta(hours=1),
    )
    # evento fuera del rango (un segundo después del borde superior)
    _seed_event_incident_alert(
        db,
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.fall,
        severity=SeverityEnum.high,
        incident_status=IncidentStatusEnum.open,
        alert_status=AlertStatusEnum.pending,
        stamp=exact + timedelta(hours=1, seconds=1),
    )
    db.commit()

    page = list_events(
        user_id=user.id,
        device_id=device.id,
        event_type=None,
        severity=None,
        date_from=exact,
        date_to=exact + timedelta(hours=1),
        order="asc",
        limit=10,
        offset=0,
        db=db,
    )

    ids = [item.id for item in page.items]
    assert ev_at_from.id in ids, "El evento en date_from deve estar incluido (>=)"
    assert ev_at_to.id in ids, "El evento en date_to debe estar incluido (<=)"
    assert page.total == 2


def test_timeline_limit_and_404(db: Session) -> None:
    now = datetime.now(UTC)
    user, device = _seed_user_device(db, name="Irene", device_code="dev-i")
    for idx in range(3):
        _seed_event_incident_alert(
            db,
            user_id=user.id,
            device_id=device.id,
            event_type=EventTypeEnum.fall,
            severity=SeverityEnum.high,
            incident_status=IncidentStatusEnum.open,
            alert_status=AlertStatusEnum.pending,
            stamp=now - timedelta(minutes=idx),
        )
    db.commit()

    timeline = get_user_timeline(user_id=user.id, limit=2, db=db)
    assert len(timeline.events) == 2
    assert len(timeline.incidents) == 2
    assert len(timeline.alerts) == 2

    with pytest.raises(HTTPException) as exc:
        get_user_timeline(user_id=999999, limit=2, db=db)
    assert exc.value.status_code == 404
    assert exc.value.detail == "User not found"
