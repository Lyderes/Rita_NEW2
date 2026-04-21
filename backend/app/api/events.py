from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from app.core.rate_limit import limiter
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import authenticate_device_for_event, require_frontend_auth
from app.core.config import get_settings
from app.db.session import get_db
from app.domain.enums import EventTypeEnum, SeverityEnum
from app.models.device import Device
from app.models.event import Event
from app.schemas.event import EventCreate, EventRead
from app.schemas.pagination import PaginatedResponse
from app.services.event_service import (
    EventSemanticValidationError,
    TraceIdConflictError,
    UnsupportedEventTypeError,
    create_event_with_side_effects,
)

router = APIRouter(tags=["events"])
logger = logging.getLogger(__name__)


@router.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an edge event",
    description=(
        "Receives an event produced by a device. Requires X-Device-Token header matching the "
        "payload device_code and active device admin status. If trace_id already exists, returns 200 "
        "with the existing event for idempotency.\n\n"
        "**user_speech events**: When `event_type=user_speech` and `user_text` is present, "
        "RITA processes the message through the conversational AI and returns her response "
        "in the `rita_text` field of the response. The Raspberry Pi should synthesize this text "
        "as voice output. If the AI is disabled or unavailable, `rita_text` contains a safe "
        "fallback phrase."
    ),
    responses={
        200: {"description": "Event already existed for trace_id (idempotent replay)"},
        201: {"description": "Event created. For user_speech, rita_text contains RITA's response."},
        401: {"description": "Missing or invalid X-Device-Token"},
        403: {"description": "Device token valid but device is not allowed to operate"},
        404: {"description": "Device not found"},
        409: {"description": "trace_id conflicts with another event payload"},
        422: {"description": "Unsupported event type or semantic validation error"},
    },
)
async def create_event(
    payload: EventCreate,
    response: Response,
    db: Session = Depends(get_db),
    authenticated_device: Device = Depends(authenticate_device_for_event),
) -> Event:
    logger.info(
        "event_ingest_received trace_id=%s device_code=%s event_type=%s source=%s",
        payload.trace_id,
        payload.device_code,
        payload.event_type.value,
        payload.source,
    )
    preexisting = db.scalar(select(Event).where(Event.trace_id == str(payload.trace_id)))
    try:
        event = create_event_with_side_effects(db, payload, device=authenticated_device)
    except UnsupportedEventTypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EventSemanticValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TraceIdConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if event is None:
        logger.warning(
            "event_ingest_failed reason=device_not_found trace_id=%s device_code=%s",
            payload.trace_id,
            payload.device_code,
        )
        raise HTTPException(status_code=404, detail="Device not found")
    if preexisting is not None:
        response.status_code = status.HTTP_200_OK

    # --- Bridge user_speech → ConversationService ---
    # Cuando el dispositivo manda user_speech con texto Y la IA está habilitada,
    # RITA responde de forma conversacional y devuelve la respuesta en rita_text
    # para que la Raspberry Pi la sintetice como voz.
    # Si la IA está deshabilitada (ENABLE_CONVERSATION_AI=false), el edge genera
    # su propia respuesta localmente y este bridge se omite.
    # Solo para eventos nuevos (no replay idempotente) con texto real.
    if (
        event.event_type == EventTypeEnum.user_speech
        and event.user_text
        and preexisting is None
        and get_settings().enable_conversation_ai
    ):
        await _handle_user_speech(db, event=event, user_id=authenticated_device.user_id)

    logger.info(
        "event_ingest_persisted event_id=%s trace_id=%s status_code=%s",
        event.id,
        event.trace_id,
        response.status_code,
    )
    return event


async def _handle_user_speech(db: Session, *, event: Event, user_id: int) -> None:
    """
    Procesa un evento user_speech a través del ConversationService y escribe
    la respuesta de RITA en event.rita_text.

    Nunca lanza excepción — ante cualquier fallo escribe un fallback en rita_text
    para que la Raspberry Pi siempre tenga algo que sintetizar.
    """
    from app.services.conversation_service import ConversationService

    _SPEECH_FALLBACK = "Estoy aquí contigo. ¿Puedes repetirlo?"

    try:
        service = ConversationService(db)
        session = await service.get_or_create_session(user_id, force_new=False)
        turn = await service.process_turn(session, event.user_text)
        rita_response = turn.response
    except Exception as exc:
        logger.error(
            "conversation_error event_id=%s user_id=%s error=%s — using fallback",
            event.id, user_id, exc,
        )
        rita_response = _SPEECH_FALLBACK

    # Actualizar rita_text en el evento original y persistir
    event.rita_text = rita_response
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.info(
        "user_speech_processed event_id=%s user_id=%s rita_text_len=%d",
        event.id, user_id, len(rita_response),
    )


@router.get(
    "/events",
    response_model=PaginatedResponse[EventRead],
    summary="List events with filters",
    description="Returns paginated events. Requires frontend Bearer JWT.",
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def list_events(
    trace_id: Annotated[
        str | None,
        Query(
        description="Filter by exact trace_id (idempotency key).",
        examples=["3f8c5238-0b7e-4d8f-9e1f-60da95bc52d9"],
        ),
    ] = None,
    user_id: int | None = Query(
        default=None,
        description="Filter by owner user id.",
        examples=[12],
    ),
    device_id: int | None = Query(
        default=None,
        description="Filter by origin device id.",
        examples=[7],
    ),
    event_type: EventTypeEnum | None = Query(
        default=None,
        description="Filter by canonical event type.",
        examples=["panic"],
    ),
    severity: SeverityEnum | None = Query(
        default=None,
        description="Filter by event severity.",
        examples=["high"],
    ),
    date_from: datetime | None = Query(
        default=None,
        description="Include events with created_at >= this timestamp (inclusive). Use ISO 8601; UTC with Z or +00:00 is recommended.",
        examples=["2026-03-16T00:00:00Z"],
    ),
    date_to: datetime | None = Query(
        default=None,
        description="Include events with created_at <= this timestamp (inclusive). Use ISO 8601; UTC with Z or +00:00 is recommended.",
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
    _: str = Depends(require_frontend_auth),
) -> PaginatedResponse[EventRead]:
    stmt: Select[tuple[Event]] = select(Event)
    if trace_id is not None:
        stmt = stmt.where(Event.trace_id == trace_id)
    if user_id is not None:
        stmt = stmt.where(Event.user_id == user_id)
    if device_id is not None:
        stmt = stmt.where(Event.device_id == device_id)
    if event_type is not None:
        stmt = stmt.where(Event.event_type == event_type)
    if severity is not None:
        stmt = stmt.where(Event.severity == severity)
    if date_from is not None:
        stmt = stmt.where(Event.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Event.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if order == "asc":
        stmt = stmt.order_by(Event.created_at.asc(), Event.id.asc())
    else:
        stmt = stmt.order_by(Event.created_at.desc(), Event.id.desc())

    stmt = stmt.limit(limit).offset(offset)
    items = [EventRead.model_validate(row) for row in db.scalars(stmt).all()]
    return PaginatedResponse[EventRead](items=items, total=total, limit=limit, offset=offset)

@router.post(
    "/events/checkin",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate a check-in event (Phase 1)",
    description="Creates a simulated check-in event for a user. Bypasses device token requirement for testing.",
    responses={
        404: {"description": "User or Device not found"},
    },
)
@limiter.limit("10/minute")
async def simulate_checkin(
    request: Request,
    user_id: int = Body(..., embed=True),
    text: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> dict:
    from app.models.user import User
    from app.schemas.event import EventCreate
    from app.services.check_in_analysis_service import CheckInAnalysisService
    from app.services.ai.rule_based_analysis import run_rule_based_analysis, normalize_analysis
    import uuid

    # 1. Input Validation
    if not text or not text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Check-in text cannot be empty")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="El usuario no existe. Selecciona un usuario válido.")

    # 2. Find device (required for Event model)
    device = db.scalar(
        select(Device).where(Device.user_id == user_id, Device.is_active).limit(1)
    )
    if not device:
        device = db.scalar(select(Device).where(Device.user_id == user_id).limit(1))
    
    if not device:
        raise HTTPException(status_code=400, detail="El usuario no tiene un dispositivo asignado. Registra uno primero para poder simular.")

    # 3. Create Event
    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid.uuid4(),
        device_code=device.device_code,
        event_type=EventTypeEnum.checkin,
        severity=SeverityEnum.low,
        source="simulation-ui",
        user_text=text.strip(),
        payload_json={"is_simulation": True}
    )

    try:
        event = create_event_with_side_effects(db, payload, device=device)
        
        # 4. Synchronous Analysis (Hardened)
        # Background analysis is disabled for "simulation-ui" source to avoid race conditions.
        service = CheckInAnalysisService(db)
        try:
            analysis_obj = await service.analyze_event_check_in(event)
            if analysis_obj:
                from app.schemas.check_in_analysis import CheckInAnalysisRead
                analysis = CheckInAnalysisRead.model_validate(analysis_obj).model_dump()
            else:
                # Fallback to rules if AI failed
                analysis = normalize_analysis(run_rule_based_analysis(text))
        except Exception as e:
            logger.error(f"Analysis failed during simulation for event {event.id}: {e}")
            analysis = normalize_analysis(run_rule_based_analysis(text))

        return {
            "id": str(event.id),
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Event creation failed during simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create simulation event: {str(e)}")

@router.post(
    "/events/{event_id}/confirm",
    response_model=EventRead,
    status_code=status.HTTP_200_OK,
    summary="Confirm a triggered reminder",
    description="Marks a 'reminder_triggered' event as confirmed and emits a 'reminder_confirmed' system event.",
    responses={
        400: {"description": "Event is not a pending reminder or already confirmed"},
        404: {"description": "Event not found"},
    },
)
def confirm_reminder_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> Event:
    import uuid
    from sqlalchemy.orm.attributes import flag_modified
    
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
        
    if event.event_type != EventTypeEnum.reminder_triggered:
        raise HTTPException(status_code=400, detail="Este evento no es un recordatorio")
        
    payload = event.payload_json or {}
    if payload.get("confirmation_status") != "pending":
        # Handle safely: if already confirmed, just return 200 (Requirement 3: verify duplicate confirmation handled safely)
        if payload.get("confirmation_status") == "confirmed":
            return event
        raise HTTPException(status_code=400, detail="Este recordatorio no requiere confirmación o ya ha sido procesado")

    # 1. Update original event
    payload["confirmation_status"] = "confirmed"
    payload["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    event.payload_json = payload
    flag_modified(event, "payload_json") # Required for SQLAlchemy to detect JSON change

    # 2. Create secondary "reminder_confirmed" event for the timeline
    confirmation_event = Event(
        trace_id=str(uuid.uuid4()),
        user_id=event.user_id,
        device_id=event.device_id,
        event_type=EventTypeEnum.reminder_confirmed,
        severity=SeverityEnum.low,
        source="rita-frontend",
        payload_json={
            "original_event_id": event.id,
            "reminder_id": payload.get("reminder_id"),
            "title": payload.get("title")
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(confirmation_event)
    db.commit()
    db.refresh(event)
    
    return event
