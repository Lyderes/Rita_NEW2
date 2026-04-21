
from __future__ import annotations

from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field

class DailyScoreBase(BaseModel):
    global_score: int = Field(ge=0, le=100)
    mood_score: int = Field(ge=0, le=100)
    activity_score: int = Field(ge=0, le=100)
    routine_score: int = Field(ge=0, le=100)
    autonomy_score: int = Field(ge=0, le=100)
    baseline_similarity: int = Field(ge=0, le=100)
    main_factors: list[str] = Field(default_factory=list)
    narrative_summary: str
    interpretation: str | None = None
    # Phase 6.5: Routine summary for dashboard display
    observed_routines: list[str] = Field(default_factory=list)
    missed_or_late_routines: list[str] = Field(default_factory=list)

class DailyScoreRead(DailyScoreBase):
    id: int
    user_id: int
    date: date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DailyScoreHistoryItem(BaseModel):
    date: date
    global_score: int
    narrative_summary: str
    
    model_config = ConfigDict(from_attributes=True)
