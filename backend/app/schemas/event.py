from __future__ import annotations

from datetime import datetime
from typing import Literal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EventTypeEnum, SeverityEnum


class EventCreate(BaseModel):
    schema_version: Literal["1.0"] = Field(
        description="Payload schema version for edge event ingestion.",
        examples=["1.0"],
    )
    trace_id: UUID = Field(
        description="Client-generated idempotency identifier for deduplication.",
        examples=["3f8c5238-0b7e-4d8f-9e1f-60da95bc52d9"],
    )
    device_code: str = Field(description="Unique device code registered in backend.", examples=["edge-001"])
    event_type: EventTypeEnum = Field(description="Canonical event type.", examples=["panic"])
    severity: SeverityEnum | None = Field(default=None, description="Severity level for the event.", examples=["high"])
    source: str = Field(default="rita-edge", description="Event producer identifier.", examples=["rita-edge"])
    user_text: str | None = Field(default=None, description="Optional transcript of user utterance.")
    rita_text: str | None = Field(default=None, description="Optional transcript of assistant response.")
    payload_json: dict[str, Any] | None = Field(
        default=None,
        description="Structured event payload with domain-specific fields.",
        examples=[{"battery": 0.72, "language": "es", "raw_event_type": "panic"}],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schema_version": "1.0",
                "trace_id": "3f8c5238-0b7e-4d8f-9e1f-60da95bc52d9",
                "device_code": "edge-001",
                "event_type": "panic",
                "severity": "high",
                "source": "rita-edge",
                "user_text": "Necesito ayuda",
                "rita_text": "He detectado una emergencia. Notificando al cuidador.",
                "payload_json": {"battery": 0.72, "language": "es"},
            }
        }
    )


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Event primary key.", examples=[101])
    trace_id: str = Field(description="Idempotency identifier.", examples=["3f8c5238-0b7e-4d8f-9e1f-60da95bc52d9"])
    user_id: int = Field(description="Owner user id.", examples=[12])
    device_id: int = Field(description="Origin device id.", examples=[7])
    event_type: EventTypeEnum = Field(description="Canonical event type.", examples=["panic"])
    severity: SeverityEnum = Field(description="Resolved event severity.", examples=["high"])
    source: str = Field(description="Event producer identifier.", examples=["rita-edge"])
    user_text: str | None = Field(default=None, description="Optional transcript of user utterance.")
    rita_text: str | None = Field(default=None, description="Optional transcript of assistant response.")
    payload_json: dict[str, Any] | None = Field(default=None, description="Structured event payload.")
    human_description: str = Field(description="Natural language description for caregivers.")
    created_at: datetime = Field(description="Creation timestamp in UTC.")
