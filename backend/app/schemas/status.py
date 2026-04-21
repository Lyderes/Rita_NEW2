from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import EventTypeEnum, IncidentStatusEnum, SeverityEnum


class OpenIncidentStatus(BaseModel):
    id: int
    incident_type: EventTypeEnum
    severity: SeverityEnum
    status: IncidentStatusEnum
    opened_at: datetime


class UserStatusRead(BaseModel):
    user_id: int
    user_name: str
    current_status: str
    last_event_type: EventTypeEnum | None
    last_event_at: datetime | None
    open_incident: OpenIncidentStatus | None
    wellbeing_score: int = Field(ge=0, le=100)
    wellbeing_state: str
