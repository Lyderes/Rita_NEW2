from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_TYPES = {"medication", "meal", "hydration", "checkin", "custom"}


class ScheduledReminderBase(BaseModel):
    reminder_type: str = Field(..., examples=["medication"], description="Type of reminder (medication, meal, hydration, etc.)")
    title: str = Field(..., examples=["Tomar Aspirina"], description="Short title for the reminder")
    description: str | None = Field(None, examples=["Después del desayuno"], description="Optional context")
    time_of_day: str = Field(..., examples=["09:00"], description="HH:mm local time format")
    days_of_week: list[str] = Field(default_factory=list, examples=[["mon", "wed", "fri"]], description="List of days for the routine")
    is_active: bool = Field(True, description="Whether the reminder is currently enabled")
    requires_confirmation: bool = Field(False, description="If RITA should expect a verbal confirmation")
    severity: str = Field("medium", examples=["high"], description="low, medium, or high")
    last_triggered_at: datetime | None = Field(None, description="Timestamp of the last time this reminder was triggered")

    @field_validator("reminder_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"Invalid reminder_type. Must be one of: {', '.join(VALID_TYPES)}")
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("days_of_week cannot be empty")
        for day in v:
            if day not in VALID_DAYS:
                raise ValueError(f"Invalid day: {day}. Must be one of: {', '.join(VALID_DAYS)}")
        return v


class ScheduledReminderCreate(ScheduledReminderBase):
    pass


class ScheduledReminderUpdate(BaseModel):
    reminder_type: str | None = None
    title: str | None = None
    description: str | None = None
    time_of_day: str | None = None
    days_of_week: list[str] | None = None
    is_active: bool | None = None
    requires_confirmation: bool | None = None
    severity: str | None = None
    last_triggered_at: datetime | None = None


class ScheduledReminderRead(ScheduledReminderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
