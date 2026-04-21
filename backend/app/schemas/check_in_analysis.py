from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class CheckInAnalysisBase(BaseModel):
    summary: str = Field(..., description="Resumen del estado del usuario")
    mood: str = Field("unknown", description="Estado de ánimo: positive, neutral, low, unknown")
    signals: list[str] = Field(default_factory=list, description="Lista de señales detectadas")
    risk: str = Field(..., description="Nivel de riesgo: low, medium, high")

class CheckInAnalysisCreate(CheckInAnalysisBase):
    event_id: int
    text: str | None = None
    model_used: str
    raw_response: dict | None = None

class CheckInAnalysisRead(CheckInAnalysisBase):
    id: int
    event_id: int
    text: str | None = None
    model_used: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
