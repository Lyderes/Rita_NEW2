from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import authenticate_device_for_path, require_frontend_auth
from app.core.security import generate_device_token, hash_device_token
from app.db.session import get_db
from app.domain.enums import AuditActorTypeEnum, AuditTargetTypeEnum
from app.models.device import Device
from app.models.user import User
from app.schemas.device_status import DeviceStatusRead
from app.schemas.device import DeviceCreate, DeviceHeartbeatRead, DeviceProvisionRead, DeviceRead
from app.services.metrics_service import increment_counter
from app.services.audit_service import record_audit_event
from app.services.device_status_service import build_device_status_list

router = APIRouter(tags=["devices"])

AUDIT_REQUIRED_ERROR_DETAIL = "Action could not be completed because required audit logging failed"


@router.post(
    "/devices",
    response_model=DeviceProvisionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a device",
    description=(
        "Creates a new device for a user and returns the plain device token once. "
        "Requires frontend Bearer JWT."
    ),
    responses={
        201: {"description": "Device created and token provisioned"},
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "User not found"},
        409: {"description": "Device code already exists"},
        503: {"description": "Required audit logging failed"},
    },
)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    actor_identifier: str = Depends(require_frontend_auth),
) -> dict:
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.scalar(select(Device).where(Device.device_code == payload.device_code))
    if existing is not None:
        raise HTTPException(status_code=409, detail="device_code already exists")

    plain_token = generate_device_token()
    device = Device(
        user_id=payload.user_id,
        device_code=payload.device_code,
        device_token_hash=hash_device_token(plain_token),
        device_name=payload.device_name,
        location_name=payload.location_name,
        is_active=payload.is_active,
    )
    db.add(device)
    try:
        record_audit_event(
            db,
            action_type="device.create",
            actor_type=AuditActorTypeEnum.frontend_user,
            actor_identifier=actor_identifier,
            target_type=AuditTargetTypeEnum.device,
            target_identifier=device.device_code,
            metadata_json={
                "user_id": device.user_id,
                "device_name": device.device_name,
                "location_name": device.location_name,
            },
        )
    except Exception as exc:
        increment_counter("audit_required_failure_total")
        db.rollback()
        raise HTTPException(status_code=503, detail=AUDIT_REQUIRED_ERROR_DETAIL) from exc

    db.refresh(device)

    data = DeviceRead.model_validate(device).model_dump()
    data["device_token"] = plain_token
    return data


@router.get(
    "/devices",
    response_model=list[DeviceRead],
    summary="List devices",
    description="Returns all registered devices. Requires frontend Bearer JWT.",
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def list_devices(db: Session = Depends(get_db), _: str = Depends(require_frontend_auth)) -> list[Device]:
    stmt = select(Device).order_by(Device.id.asc())
    return list(db.scalars(stmt).all())


@router.get(
    "/devices/status",
    response_model=list[DeviceStatusRead],
    summary="List device operational status",
    description="Returns online/stale/offline status projection for devices. Requires frontend Bearer JWT.",
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def list_devices_status(
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> list[DeviceStatusRead]:
    return build_device_status_list(db)


@router.post(
    "/devices/{device_code}/heartbeat",
    response_model=DeviceHeartbeatRead,
    summary="Submit device heartbeat",
    description=(
        "Updates the last heartbeat timestamp for a device. Requires X-Device-Token header and "
        "device admin_status=active."
    ),
    responses={
        200: {"description": "Heartbeat accepted"},
        401: {"description": "Missing or invalid X-Device-Token"},
        403: {"description": "Device token valid but device is not allowed to operate"},
        404: {"description": "Device not found"},
    },
)
def device_heartbeat(
    device_code: str,
    db: Session = Depends(get_db),
    device: Device = Depends(authenticate_device_for_path),
) -> Device:
    device.last_seen_at = datetime.now(timezone.utc)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.post(
    "/devices/{device_code}/rotate-token",
    response_model=DeviceProvisionRead,
    summary="Rotate device token",
    description=(
        "Rotates the device token and returns the new plain token once. Requires frontend Bearer JWT "
        "and required audit logging."
    ),
    responses={
        200: {"description": "Token rotated"},
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "Device not found"},
        503: {"description": "Required audit logging failed"},
    },
)
def rotate_device_token(
    device_code: str,
    db: Session = Depends(get_db),
    actor_identifier: str = Depends(require_frontend_auth),
) -> dict:
    device = db.scalar(select(Device).where(Device.device_code == device_code))
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    plain_token = generate_device_token()
    device.device_token_hash = hash_device_token(plain_token)
    device.token_rotated_at = datetime.now(timezone.utc)
    db.add(device)
    try:
        record_audit_event(
            db,
            action_type="device.rotate_token",
            actor_type=AuditActorTypeEnum.frontend_user,
            actor_identifier=actor_identifier,
            target_type=AuditTargetTypeEnum.device,
            target_identifier=device.device_code,
            metadata_json={"token_rotated": True},
        )
    except Exception as exc:
        increment_counter("audit_required_failure_total")
        db.rollback()
        raise HTTPException(status_code=503, detail=AUDIT_REQUIRED_ERROR_DETAIL) from exc

    db.refresh(device)

    data = DeviceRead.model_validate(device).model_dump()
    data["device_token"] = plain_token
    return data
