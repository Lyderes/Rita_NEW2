from __future__ import annotations

from pydantic import BaseModel

from app.schemas.alert import AlertRead
from app.schemas.device_status import DeviceStatusRead
from app.schemas.event import EventRead
from app.schemas.status import OpenIncidentStatus


class UserOverviewRead(BaseModel):
    user_id: int
    user_name: str
    current_status: str
    last_event: EventRead | None
    open_incident: OpenIncidentStatus | None
    pending_alerts: int
    devices: list[DeviceStatusRead]
    recent_events: list[EventRead]
    recent_alerts: list[AlertRead]