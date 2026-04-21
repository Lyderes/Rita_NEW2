from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Body, Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token, hash_device_token, verify_device_token
from app.db.session import get_db
from app.domain.enums import DeviceAdminStatusEnum
from app.models.device import Device
from app.models.user import User
from app.schemas.event import EventCreate
from app.services.metrics_service import increment_counter

bearer_scheme = HTTPBearer(auto_error=False)
device_token_header = APIKeyHeader(name="X-Device-Token", auto_error=False)
logger = logging.getLogger(__name__)


def require_frontend_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Sanitize token input (stripping whitespace/newlines)
    raw_token = credentials.credentials.strip()
    try:
        payload = decode_access_token(raw_token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return subject


def _require_device_header(device_token: str | None) -> str:
    if device_token is None or not device_token.strip():
        increment_counter("device_auth_failed_total")
        logger.warning("device_auth_failed reason=missing_header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Device-Token header",
        )
    return device_token.strip()


def _ensure_device_admin_active(device: Device) -> None:
    if device.admin_status != DeviceAdminStatusEnum.active:
        increment_counter("device_forbidden_total")
        logger.warning(
            "device_forbidden reason=admin_status_not_active device_code=%s admin_status=%s",
            device.device_code,
            device.admin_status.value,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device is not allowed to operate (admin_status={device.admin_status.value})",
        )


def _autoprovision_edge_device(
    *,
    db: Session,
    payload: EventCreate,
    provided_token: str,
) -> Device | None:
    settings = get_settings()
    if not settings.auto_provision_edge_devices:
        return None

    logger.warning(
        "device_autoprovision_requested device_code=%s source=%s",
        payload.device_code,
        payload.source,
    )
    user = db.scalar(select(User).order_by(User.id.asc()))
    if user is None:
        user = User(full_name="RITA Edge Demo User", notes="Auto-created for local edge event ingestion")
        db.add(user)
        db.flush()
        logger.info("autoprovision_user_created user_id=%s", user.id)

    device = Device(
        user_id=user.id,
        device_code=payload.device_code,
        device_name="RITA Edge",
        location_name="Modo local",
        admin_status=DeviceAdminStatusEnum.active,
        device_token_hash=hash_device_token(provided_token),
        is_active=True,
    )
    db.add(device)
    db.flush()
    logger.info(
        "autoprovision_device_created device_id=%s device_code=%s user_id=%s",
        device.id,
        device.device_code,
        device.user_id,
    )
    return device


def authenticate_device_for_event(
    payload: Annotated[EventCreate, Body(...)],
    db: Session = Depends(get_db),
    device_token: str | None = Depends(device_token_header),
) -> Device:
    provided_token = _require_device_header(device_token)
    logger.info("event_auth_attempt device_code=%s trace_id=%s", payload.device_code, payload.trace_id)
    device = db.scalar(select(Device).where(Device.device_code == payload.device_code))
    if device is None:
        device = _autoprovision_edge_device(db=db, payload=payload, provided_token=provided_token)
    if device is None:
        logger.warning("device_auth_failed reason=device_not_found device_code=%s", payload.device_code)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    if not verify_device_token(device.device_token_hash, provided_token):
        increment_counter("device_auth_failed_total")
        logger.warning("device_auth_failed reason=invalid_token device_code=%s", payload.device_code)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device token")
    _ensure_device_admin_active(device)
    return device


def authenticate_device_for_path(
    device_code: str,
    db: Session = Depends(get_db),
    device_token: str | None = Depends(device_token_header),
) -> Device:
    provided_token = _require_device_header(device_token)
    device = db.scalar(select(Device).where(Device.device_code == device_code))
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    if not verify_device_token(device.device_token_hash, provided_token):
        increment_counter("device_auth_failed_total")
        logger.warning("device_auth_failed reason=invalid_token device_code=%s", device_code)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device token")
    _ensure_device_admin_active(device)
    return device
