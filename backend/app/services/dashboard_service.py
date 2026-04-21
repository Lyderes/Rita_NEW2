from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import AlertStatusEnum, IncidentStatusEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.user import User
from app.models.incident import Incident
from app.schemas.alert import AlertRead
from app.schemas.dashboard import DashboardRead
from app.schemas.event import EventRead
from app.schemas.overview import UserOverviewRead
from app.services.device_status_service import build_device_status_list, get_connection_status
from app.services.status_service import build_user_status


def build_dashboard_summary(db: Session) -> DashboardRead:
    users_total = db.scalar(select(func.count()).select_from(User)) or 0
    devices_total = db.scalar(select(func.count()).select_from(Device)) or 0
    devices_active = db.scalar(select(func.count()).select_from(Device).where(Device.is_active.is_(True))) or 0
    incidents_open = (
        db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status == IncidentStatusEnum.open)
        )
        or 0
    )
    alerts_pending = (
        db.scalar(select(func.count()).select_from(Alert).where(Alert.status == AlertStatusEnum.pending)) or 0
    )

    device_last_seen_values = list(db.scalars(select(Device.last_seen_at)).all())
    devices_online = sum(1 for value in device_last_seen_values if get_connection_status(value) == "online")

    last_event = db.scalar(select(Event).order_by(Event.created_at.desc(), Event.id.desc()))

    return DashboardRead(
        users_total=users_total,
        devices_total=devices_total,
        devices_active=devices_active,
        devices_online=devices_online,
        incidents_open=incidents_open,
        alerts_pending=alerts_pending,
        last_event_at=last_event.created_at if last_event else None,
        last_event_type=last_event.event_type if last_event else None,
    )


def build_user_overview(db: Session, user_id: int) -> UserOverviewRead | None:
    user = db.get(User, user_id)
    if user is None:
        return None

    status_out = build_user_status(db, user_id)
    last_event = db.scalar(
        select(Event)
        .where(Event.user_id == user_id)
        .order_by(Event.created_at.desc(), Event.id.desc())
    )
    recent_events = list(
        db.scalars(
            select(Event)
            .where(Event.user_id == user_id)
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(5)
        ).all()
    )
    recent_alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc(), Alert.id.desc())
            .limit(5)
        ).all()
    )
    pending_alerts = (
        db.scalar(
            select(func.count()).select_from(Alert).where(
                Alert.user_id == user_id,
                Alert.status == AlertStatusEnum.pending,
            )
        )
        or 0
    )
    devices = build_device_status_list(db, user_id=user_id)
    last_event_out = EventRead.model_validate(last_event) if last_event else None

    return UserOverviewRead(
        user_id=user.id,
        user_name=user.full_name,
        current_status=status_out.current_status if status_out else "ok",
        last_event=last_event_out,
        open_incident=status_out.open_incident if status_out else None,
        pending_alerts=pending_alerts,
        devices=devices,
        recent_events=[EventRead.model_validate(event) for event in recent_events],
        recent_alerts=[AlertRead.model_validate(alert) for alert in recent_alerts],
    )