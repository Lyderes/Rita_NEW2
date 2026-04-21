from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AlertStatusEnum, EventTypeEnum, SeverityEnum


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Alert primary key.", examples=[88])
    user_id: int = Field(description="Related user id.", examples=[12])
    incident_id: int = Field(description="Related incident id.", examples=[41])
    event_id: int | None = Field(default=None, description="Related event id, if any.")
    alert_type: EventTypeEnum = Field(description="Alert type.", examples=["panic"])
    severity: SeverityEnum = Field(description="Alert severity.", examples=["high"])
    status: AlertStatusEnum = Field(description="Current alert status.", examples=["new"])
    message: str = Field(description="Rendered alert message for operators.")
    created_at: datetime = Field(description="Alert creation timestamp in UTC.")
    sent_at: datetime | None = Field(default=None, description="Notification delivery timestamp in UTC.")
    escalation_required: bool = Field(default=False, description="True when alert exceeded pending SLA and requires escalation.")
    escalated_at: datetime | None = Field(default=None, description="Escalation timestamp in UTC, if escalated.")
    escalation_count: int = Field(default=0, description="How many escalation actions have been applied to this alert.")


class AlertAcknowledgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Alert id.", examples=[88])
    status: AlertStatusEnum = Field(description="Resulting alert status.", examples=["acknowledged"])
    sent_at: datetime | None = Field(default=None, description="Notification delivery timestamp in UTC.")
    escalation_required: bool = Field(default=False, description="True when alert exceeded pending SLA and requires escalation.")
    escalated_at: datetime | None = Field(default=None, description="Escalation timestamp in UTC, if escalated.")
    escalation_count: int = Field(default=0, description="How many escalation actions have been applied to this alert.")
