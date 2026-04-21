from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class UserInterpretationSettingsBase(BaseModel):
    sensitivity_mode: str = Field(default="balanced", description="Sensitivity mode: calm, balanced, sensitive")
    has_chronic_pain: bool = Field(default=False)
    low_energy_baseline: bool = Field(default=False)
    mood_variability: bool = Field(default=False)
    low_communication: bool = Field(default=False)


class UserInterpretationSettingsUpdate(UserInterpretationSettingsBase):
    pass


class UserInterpretationSettingsRead(UserInterpretationSettingsBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
