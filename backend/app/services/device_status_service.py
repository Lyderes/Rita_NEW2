from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.user import User
from app.schemas.device_status import DeviceStatusRead

ONLINE_WINDOW_MINUTES = 5
STALE_WINDOW_MINUTES = 30


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_connection_status(last_seen_at: datetime | None, *, now: datetime | None = None) -> str:
    normalized = _normalize_timestamp(last_seen_at)
    if normalized is None:
        return "offline"

    current_time = now or datetime.now(UTC)
    age = current_time - normalized
    if age <= timedelta(minutes=ONLINE_WINDOW_MINUTES):
        return "online"
    if age <= timedelta(minutes=STALE_WINDOW_MINUTES):
        return "stale"
    return "offline"


def build_device_status_list(db: Session, *, user_id: int | None = None) -> list[DeviceStatusRead]:
    stmt: Select[tuple[Device, User.full_name]] = (
        select(Device, User.full_name)
        .join(User, User.id == Device.user_id)
        .order_by(User.full_name.asc(), Device.id.asc())
    )
    if user_id is not None:
        stmt = stmt.where(Device.user_id == user_id)

    now = datetime.now(UTC)
    rows = db.execute(stmt).all()
    return [
        DeviceStatusRead(
            id=device.id,
            device_code=device.device_code,
            device_name=device.device_name,
            user_id=device.user_id,
            user_name=user_name,
            is_active=device.is_active,
            last_seen_at=device.last_seen_at,
            connection_status=get_connection_status(device.last_seen_at, now=now),
        )
        for device, user_name in rows
    ]