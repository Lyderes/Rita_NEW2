from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import EventTypeEnum


class DashboardRead(BaseModel):
    users_total: int
    devices_total: int
    devices_active: int
    devices_online: int
    incidents_open: int
    alerts_pending: int
    last_event_at: datetime | None
    last_event_type: EventTypeEnum | None