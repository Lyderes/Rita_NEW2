from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter

from app.core.security import (
    create_access_token,
    hash_password,
    verify_frontend_credentials,
    verify_password,
)
from app.api.deps import require_frontend_auth
from app.db.session import get_db
from app.domain.enums import AuditActorTypeEnum, AuditTargetTypeEnum
from app.models.frontend_user import FrontendUser
from app.schemas.auth import LoginRequest, MeRead, PushTokenUpdate, RegisterRequest, TokenRead
from app.services.audit_service import try_record_audit_event

router = APIRouter(tags=["auth"])


def _authenticate_login(username: str, password: str, db: Session) -> bool:
    db_user = db.scalar(select(FrontendUser).where(FrontendUser.username == username))
    if db_user is not None:
        return verify_password(password, db_user.password_hash)
    return verify_frontend_credentials(username, password)


@router.post(
    "/auth/login",
    response_model=TokenRead,
    summary="Authenticate frontend user",
    description=(
        "Authenticates a frontend operator using username/password and returns a Bearer JWT. "
        "Login audit events are best-effort and do not block authentication."
    ),
    responses={
        200: {
            "description": "Authenticated successfully",
            "content": {
                "application/json": {
                    "example": {"access_token": "<jwt>", "token_type": "bearer"}
                }
            },
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {
                        "error": "unauthorized",
                        "message": "Invalid credentials",
                        "code": 401,
                        "request_id": "c6a9f3b2-32fd-48b2-8d4f-f3f0ff5a5c9a",
                    }
                }
            },
        },
        422: {
            "description": "Malformed login payload",
            "content": {
                "application/json": {
                    "example": {
                        "error": "validation_error",
                        "message": "body -> username: Field required",
                        "code": 422,
                        "request_id": "c6a9f3b2-32fd-48b2-8d4f-f3f0ff5a5c9a",
                    }
                }
            },
        },
    },
)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenRead:
    if not _authenticate_login(payload.username, payload.password, db):
        try_record_audit_event(
            db,
            action_type="auth.login.failed",
            actor_type=AuditActorTypeEnum.frontend_user,
            actor_identifier=payload.username,
            target_type=AuditTargetTypeEnum.frontend_auth,
            target_identifier=payload.username,
            metadata_json={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    try_record_audit_event(
        db,
        action_type="auth.login.success",
        actor_type=AuditActorTypeEnum.frontend_user,
        actor_identifier=payload.username,
        target_type=AuditTargetTypeEnum.frontend_auth,
        target_identifier=payload.username,
        metadata_json={"result": "success"},
    )
    return TokenRead(access_token=create_access_token(subject=payload.username))


@router.post(
    "/auth/register",
    response_model=TokenRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register frontend user",
    description=(
        "Registers a new frontend operator account with username/password and returns a Bearer JWT. "
        "This endpoint performs automatic login by returning access_token immediately."
    ),
    responses={
        201: {
            "description": "Registered successfully",
            "content": {
                "application/json": {
                    "example": {"access_token": "<jwt>", "token_type": "bearer"}
                }
            },
        },
        409: {
            "description": "Username already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "conflict",
                        "message": "Username already exists",
                        "code": 409,
                        "request_id": "c6a9f3b2-32fd-48b2-8d4f-f3f0ff5a5c9a",
                    }
                }
            },
        },
    },
)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenRead:
    existing = db.scalar(select(FrontendUser).where(FrontendUser.username == payload.username))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = FrontendUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip() if payload.full_name else None,
    )
    db.add(user)
    db.commit()

    try_record_audit_event(
        db,
        action_type="auth.register.success",
        actor_type=AuditActorTypeEnum.frontend_user,
        actor_identifier=payload.username,
        target_type=AuditTargetTypeEnum.frontend_auth,
        target_identifier=payload.username,
        metadata_json={"result": "success"},
    )

    return TokenRead(access_token=create_access_token(subject=payload.username))


@router.get(
    "/auth/me",
    response_model=MeRead,
    summary="Get current user info",
    description="Returns basic profile info for the authenticated frontend operator.",
)
def me(
    username: str = Depends(require_frontend_auth),
    db: Session = Depends(get_db),
) -> MeRead:
    user = db.scalar(select(FrontendUser).where(FrontendUser.username == username))
    if user is None:
        return MeRead(username=username, full_name=None, has_push_token=False)
    return MeRead(
        username=user.username,
        full_name=user.full_name,
        has_push_token=user.fcm_token is not None,
    )


@router.put(
    "/auth/me/push-token",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Register or unregister FCM push token",
    description=(
        "Stores the FCM registration token for the authenticated operator so that "
        "push notifications can be delivered to their device. "
        "Send null to unregister (e.g. on logout)."
    ),
)
def update_push_token(
    payload: PushTokenUpdate,
    username: str = Depends(require_frontend_auth),
    db: Session = Depends(get_db),
) -> None:
    user = db.scalar(select(FrontendUser).where(FrontendUser.username == username))
    if user is None:
        return
    user.fcm_token = payload.token
    db.commit()
