from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EventTypeEnum, IncidentStatusEnum, SeverityEnum


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Incident primary key.", examples=[41])
    user_id: int = Field(description="Related user id.", examples=[12])
    device_id: int = Field(description="Origin device id.", examples=[7])
    event_id: int | None = Field(default=None, description="Related event id, if any.")
    incident_type: EventTypeEnum = Field(description="Incident type derived from event taxonomy.", examples=["panic"])
    status: IncidentStatusEnum = Field(description="Current incident status.", examples=["open"])
    severity: SeverityEnum = Field(description="Incident severity.", examples=["high"])
    location: str | None = Field(default=None, description="Location context, if available.")
    can_call: bool | None = Field(default=None, description="Whether direct calling is feasible.")
    summary: str | None = Field(default=None, description="Human-readable incident summary.")
    opened_at: datetime = Field(description="Incident opening timestamp in UTC.")
    closed_at: datetime | None = Field(default=None, description="Incident closing timestamp in UTC.")


class IncidentCloseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Incident id.", examples=[41])
    status: IncidentStatusEnum = Field(description="Resulting status.", examples=["closed"])
    closed_at: datetime | None = Field(default=None, description="Closing timestamp in UTC.")
