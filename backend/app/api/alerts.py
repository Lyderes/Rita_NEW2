from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_frontend_auth
from app.db.session import get_db
from app.domain.enums import AlertStatusEnum, AuditActorTypeEnum, EventTypeEnum, SeverityEnum
from app.models.alert import Alert
from app.schemas.alert import AlertAcknowledgeRead, AlertRead
from app.schemas.pagination import PaginatedResponse
from app.services.metrics_service import increment_counter
from app.services.audit_service import record_audit_event
from app.services.state_transition_service import InvalidStateTransitionError, apply_alert_transition

router = APIRouter(tags=["alerts"], dependencies=[Depends(require_frontend_auth)])

AUDIT_REQUIRED_ERROR_DETAIL = "Action could not be completed because required audit logging failed"


@router.get(
    "/alerts",
    response_model=PaginatedResponse[AlertRead],
    summary="List alerts with filters",
    description="Returns paginated alerts. Requires frontend Bearer JWT.",
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def list_alerts(
    user_id: int | None = Query(
        default=None,
        description="Filter by related user id.",
        examples=[12],
    ),
    alert_type: EventTypeEnum | None = Query(
        default=None,
        description="Filter by alert type.",
        examples=["panic"],
    ),
    status: AlertStatusEnum | None = Query(
        default=None,
        description="Filter by alert workflow status.",
        examples=["pending"],
    ),
    severity: SeverityEnum | None = Query(
        default=None,
        description="Filter by alert severity.",
        examples=["high"],
    ),
    date_from: datetime | None = Query(
        default=None,
        description="Include alerts with created_at >= this timestamp (inclusive). Use ISO 8601; UTC with Z or +00:00 is recommended.",
        examples=["2026-03-16T00:00:00Z"],
    ),
    date_to: datetime | None = Query(
        default=None,
        description="Include alerts with created_at <= this timestamp (inclusive). Use ISO 8601; UTC with Z or +00:00 is recommended.",
        examples=["2026-03-16T23:59:59Z"],
    ),
    order: Literal["asc", "desc"] = Query(
        default="desc",
        description="Sort by created_at then id. Allowed values: asc, desc.",
        examples=["desc"],
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Page size (1-200). Default: 50.",
        examples=[50],
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip for pagination. Default: 0.",
        examples=[0],
    ),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AlertRead]:
    stmt: Select[tuple[Alert]] = select(Alert)
    if user_id is not None:
        stmt = stmt.where(Alert.user_id == user_id)
    if alert_type is not None:
        stmt = stmt.where(Alert.alert_type == alert_type)
    if status is not None:
        stmt = stmt.where(Alert.status == status)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if date_from is not None:
        stmt = stmt.where(Alert.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Alert.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if order == "asc":
        stmt = stmt.order_by(Alert.created_at.asc(), Alert.id.asc())
    else:
        stmt = stmt.order_by(Alert.created_at.desc(), Alert.id.desc())

    stmt = stmt.limit(limit).offset(offset)
    items = [AlertRead.model_validate(row) for row in db.scalars(stmt).all()]
    return PaginatedResponse[AlertRead](items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/alerts/{alert_id}",
    response_model=AlertRead,
    summary="Get alert by id",
    description="Returns alert details. Requires frontend Bearer JWT.",
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "Alert not found"},
    },
)
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertAcknowledgeRead,
    summary="Acknowledge alert",
    description=(
        "Transitions an alert to acknowledged state. Repeated acknowledge is idempotent. "
        "Requires frontend Bearer JWT and required audit logging."
    ),
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "Alert not found"},
        409: {"description": "Invalid state transition"},
        503: {"description": "Required audit logging failed"},
    },
)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    actor_identifier: str = Depends(require_frontend_auth),
) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        state_changed = apply_alert_transition(alert, AlertStatusEnum.acknowledged)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if state_changed:
        db.add(alert)
        try:
            record_audit_event(
                db,
                action_type="alert.acknowledge",
                actor_type=AuditActorTypeEnum.frontend_user,
                actor_identifier=actor_identifier,
                target_type="alert",
                target_identifier=str(alert.id),
                metadata_json={"status": AlertStatusEnum.acknowledged.value},
            )
        except Exception as exc:
            increment_counter("audit_required_failure_total")
            db.rollback()
            raise HTTPException(status_code=503, detail=AUDIT_REQUIRED_ERROR_DETAIL) from exc

        db.refresh(alert)

    return alert


@router.patch(
    "/alerts/{alert_id}/resolve",
    response_model=AlertAcknowledgeRead,
    summary="Resolve alert",
    description=(
        "Transitions an alert to resolved state. Repeated resolve is idempotent. "
        "Requires frontend Bearer JWT and required audit logging."
    ),
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "Alert not found"},
        409: {"description": "Invalid state transition"},
        503: {"description": "Required audit logging failed"},
    },
)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    actor_identifier: str = Depends(require_frontend_auth),
) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        state_changed = apply_alert_transition(alert, AlertStatusEnum.resolved)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if state_changed:
        db.add(alert)
        try:
            record_audit_event(
                db,
                action_type="alert.resolve",
                actor_type=AuditActorTypeEnum.frontend_user,
                actor_identifier=actor_identifier,
                target_type="alert",
                target_identifier=str(alert.id),
                metadata_json={"status": AlertStatusEnum.resolved.value},
            )
        except Exception as exc:
            increment_counter("audit_required_failure_total")
            db.rollback()
            raise HTTPException(status_code=503, detail=AUDIT_REQUIRED_ERROR_DETAIL) from exc

        db.refresh(alert)

    return alert
