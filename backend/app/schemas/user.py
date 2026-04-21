from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    full_name: str
    birth_date: date | None = None
    notes: str | None = None
    profile_image_url: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    birth_date: date | None = None
    notes: str | None = None
    profile_image_url: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    birth_date: date | None
    notes: str | None
    profile_image_url: str | None
    created_at: datetime


class UserDailyScore(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    global_score: int
    mood_score: int
    activity_score: int
    routine_score: int
    autonomy_score: int
    baseline_similarity: int
    main_factors: list[str]
    narrative_summary: str
    interpretation: str | None = None
    updated_at: datetime
