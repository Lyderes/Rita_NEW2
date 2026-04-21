from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_frontend_auth
from app.db.session import get_db
from app.domain.enums import AuditActorTypeEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.models.incident import Incident
from app.schemas.incident import IncidentCloseRead, IncidentRead
from app.schemas.pagination import PaginatedResponse
from app.services.metrics_service import increment_counter
from app.services.audit_service import record_audit_event
from app.services.state_transition_service import InvalidStateTransitionError, apply_incident_transition

router = APIRouter(tags=["incidents"], dependencies=[Depends(require_frontend_auth)])

AUDIT_REQUIRED_ERROR_DETAIL = "Action could not be completed because required audit logging failed"


@router.get(
    "/incidents",
    response_model=PaginatedResponse[IncidentRead],
    summary="List incidents with filters",
    description="Returns paginated incidents. Requires frontend Bearer JWT.",
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def list_incidents(
    user_id: int | None = Query(
        default=None,
        description="Filter by related user id.",
        examples=[12],
    ),
    device_id: int | None = Query(
        default=None,
        description="Filter by related device id.",
        examples=[7],
    ),
    incident_type: EventTypeEnum | None = Query(
        default=None,
        description="Filter by incident type.",
        examples=["panic"],
    ),
    status: IncidentStatusEnum | None = Query(
        default=None,
        description="Filter by incident workflow status.",
        examples=["open"],
    ),
    severity: SeverityEnum | None = Query(
        default=None,
        description="Filter by incident severity.",
        examples=["high"],
    ),
    date_from: datetime | None = Query(
        default=None,
        description="Include incidents with opened_at >= this timestamp (inclusive). Use ISO 8601; UTC with Z or +00:00 is recommended.",
        examples=["2026-03-16T00:00:00Z"],
    ),
    date_to: datetime | None = Query(
        default=None,
        description="Include incidents with opened_at <= this timestamp (inclusive). Use ISO 8601; UTC with Z or +00:00 is recommended.",
        examples=["2026-03-16T23:59:59Z"],
    ),
    order: Literal["asc", "desc"] = Query(
        default="desc",
        description="Sort by opened_at then id. Allowed values: asc, desc.",
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
) -> PaginatedResponse[IncidentRead]:
    stmt: Select[tuple[Incident]] = select(Incident)
    if user_id is not None:
        stmt = stmt.where(Incident.user_id == user_id)
    if device_id is not None:
        stmt = stmt.where(Incident.device_id == device_id)
    if incident_type is not None:
        stmt = stmt.where(Incident.incident_type == incident_type)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)
    if date_from is not None:
        stmt = stmt.where(Incident.opened_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Incident.opened_at <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if order == "asc":
        stmt = stmt.order_by(Incident.opened_at.asc(), Incident.id.asc())
    else:
        stmt = stmt.order_by(Incident.opened_at.desc(), Incident.id.desc())

    stmt = stmt.limit(limit).offset(offset)
    items = [IncidentRead.model_validate(row) for row in db.scalars(stmt).all()]
    return PaginatedResponse[IncidentRead](items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentRead,
    summary="Get incident by id",
    description="Returns incident details. Requires frontend Bearer JWT.",
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "Incident not found"},
    },
)
def get_incident(incident_id: int, db: Session = Depends(get_db)) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch(
    "/incidents/{incident_id}/close",
    response_model=IncidentCloseRead,
    summary="Close incident",
    description=(
        "Transitions an incident to closed state. Repeated close is idempotent. "
        "Requires frontend Bearer JWT and required audit logging."
    ),
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "Incident not found"},
        409: {"description": "Invalid state transition"},
        503: {"description": "Required audit logging failed"},
    },
)
def close_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    actor_identifier: str = Depends(require_frontend_auth),
) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        state_changed = apply_incident_transition(incident, IncidentStatusEnum.closed)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if state_changed:
        if incident.closed_at is None:
            incident.closed_at = datetime.now(timezone.utc)
        db.add(incident)
        try:
            record_audit_event(
                db,
                action_type="incident.close",
                actor_type=AuditActorTypeEnum.frontend_user,
                actor_identifier=actor_identifier,
                target_type="incident",
                target_identifier=str(incident.id),
                metadata_json={"status": IncidentStatusEnum.closed.value},
            )
        except Exception as exc:
            increment_counter("audit_required_failure_total")
            db.rollback()
            raise HTTPException(status_code=503, detail=AUDIT_REQUIRED_ERROR_DETAIL) from exc

        db.refresh(incident)

    return incident
