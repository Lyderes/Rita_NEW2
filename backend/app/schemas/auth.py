from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(description="Frontend operator username.", examples=["operator"])
    password: str = Field(description="Frontend operator password.", examples=["change-me"])

    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "operator", "password": "change-me"}}
    )


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=100,
        description="Unique frontend username.",
        examples=["operator_new"],
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Frontend password.",
        examples=["change-me-now"],
    )
    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Optional display name for frontend operator.",
        examples=["Operator One"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "operator_new",
                "password": "change-me-now",
                "full_name": "Operator One",
            }
        }
    )


class TokenRead(BaseModel):
    access_token: str = Field(description="JWT access token to send in Authorization header.")
    token_type: str = Field(default="bearer", description="Token type for Authorization scheme.")


class PushTokenUpdate(BaseModel):
    token: str | None = Field(
        description="FCM registration token from the device. Pass null to unregister.",
        examples=["fGH3k..."],
    )


class MeRead(BaseModel):
    username: str
    full_name: str | None
    has_push_token: bool = Field(description="Whether an FCM push token is registered.")
