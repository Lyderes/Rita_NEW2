
from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

# Categorical Types
MoodType = Literal["positive", "neutral", "low"]
LevelType = Literal["low", "medium", "high"]

class UserBaselineProfileBase(BaseModel):
    usual_mood: MoodType = Field(default="neutral")
    usual_activity_level: LevelType = Field(default="medium")
    usual_energy_level: LevelType = Field(default="medium")
    lives_alone: bool = Field(default=True)
    meals_per_day: int = Field(default=3, ge=0, le=10)
    usual_sleep_hours: float = Field(default=8.0, ge=0.0, le=24.0)
    social_interaction_level: LevelType = Field(default="medium")
    notes: str | None = Field(default=None)

class UserBaselineProfileUpdate(UserBaselineProfileBase):
    pass

class UserBaselineProfileRead(UserBaselineProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
