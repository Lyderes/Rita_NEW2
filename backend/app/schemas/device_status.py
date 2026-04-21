from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DeviceStatusRead(BaseModel):
    id: int
    device_code: str
    device_name: str
    user_id: int
    user_name: str
    is_active: bool
    last_seen_at: datetime | None
    connection_status: Literal["online", "stale", "offline"]