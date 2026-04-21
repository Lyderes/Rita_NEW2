from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import DeviceAdminStatusEnum


class DeviceCreate(BaseModel):
    user_id: int = Field(description="Owner user id.", examples=[12])
    device_code: str = Field(description="Unique immutable code for edge device.", examples=["edge-001"])
    device_name: str = Field(description="Display name for operators.", examples=["RITA Sala"])
    location_name: str | None = Field(default=None, description="Optional physical location label.", examples=["Sala principal"])
    is_active: bool = Field(default=True, description="Operational active flag.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": 12,
                "device_code": "edge-001",
                "device_name": "RITA Sala",
                "location_name": "Sala principal",
                "is_active": True,
            }
        }
    )


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Device primary key.", examples=[7])
    user_id: int = Field(description="Owner user id.", examples=[12])
    device_code: str = Field(description="Unique device code.", examples=["edge-001"])
    device_name: str = Field(description="Human-friendly device name.", examples=["RITA Sala"])
    location_name: str | None = Field(default=None, description="Optional location label.")
    admin_status: DeviceAdminStatusEnum = Field(description="Administrative status gate.", examples=["active"])
    admin_status_reason: str | None = Field(default=None, description="Reason for current admin status, if any.")
    is_active: bool = Field(description="Operational flag.")
    last_seen_at: datetime | None = Field(default=None, description="Latest heartbeat timestamp in UTC.")
    created_at: datetime = Field(description="Device creation timestamp in UTC.")
    has_device_token: bool = Field(description="Whether a device token hash is stored.")


class DeviceProvisionRead(DeviceRead):
    """Returned only at creation/rotation. Exposes the plain token once."""

    device_token: str = Field(description="Plain token returned only once; store securely.")


class DeviceHeartbeatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Device id.", examples=[7])
    device_code: str = Field(description="Device code.", examples=["edge-001"])
    last_seen_at: datetime | None = Field(default=None, description="Updated heartbeat timestamp in UTC.")
    is_active: bool = Field(description="Current active flag.")
