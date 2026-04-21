"""
API endpoints del sistema conversacional de RITA.

Rutas:
  POST /users/{user_id}/conversations          → crear/reanudar sesión
  POST /conversations/{session_id}/turns       → procesar turno (principal)
  GET  /conversations/{session_id}             → historial de sesión
  GET  /users/{user_id}/conversations          → lista de sesiones
  GET  /users/{user_id}/memories               → memoria persistente
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.rate_limit import limiter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_frontend_auth
from app.domain.enums import ConversationStatusEnum
from app.models.conversation_memory import ConversationMemory
from app.models.conversation_message import ConversationMessage
from app.models.conversation_session import ConversationSession
from app.models.user import User
from app.schemas.conversation import (
    ConversationMemoryRead,
    ConversationMessageRead,
    ConversationSessionRead,
    ConversationStartRequest,
    ConversationTurnRequest,
    ConversationTurnResponse,
)
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["conversations"])


def _get_user_or_404(user_id: int, db: Session) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_session_or_404(session_id: int, db: Session) -> ConversationSession:
    session = db.get(ConversationSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation session not found"
        )
    return session


@router.post(
    "/users/{user_id}/conversations",
    response_model=ConversationSessionRead,
    status_code=status.HTTP_200_OK,
    summary="Crear o reanudar sesión conversacional",
    description=(
        "Devuelve la sesión activa del usuario si existe y no ha expirado por inactividad. "
        "Crea una nueva sesión si no hay ninguna activa o si `force_new=true`. "
        "Una sesión inactiva más de `conversation_session_idle_timeout_hours` se cierra automáticamente."
    ),
)
async def start_or_resume_session(
    user_id: int,
    payload: ConversationStartRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> ConversationSessionRead:
    _get_user_or_404(user_id, db)
    service = ConversationService(db)
    session = await service.get_or_create_session(user_id, force_new=payload.force_new)
    db.commit()
    db.refresh(session)
    return ConversationSessionRead.model_validate(session)


@router.post(
    "/conversations/{session_id}/turns",
    response_model=ConversationTurnResponse,
    summary="Procesar turno conversacional",
    description=(
        "Recibe el mensaje del usuario y devuelve la respuesta de RITA. "
        "Internamente: construye el contexto con perfil + memoria + historial, "
        "llama a Claude, valida la salida, persiste el turno y evalúa señales. "
        "Si el sistema de IA está deshabilitado (`ENABLE_CONVERSATION_AI=false`) "
        "devuelve una respuesta de fallback genérica."
    ),
)
@limiter.limit("30/minute")
async def process_turn(
    request: Request,
    session_id: int,
    payload: ConversationTurnRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> ConversationTurnResponse:
    session = _get_session_or_404(session_id, db)

    if session.status != ConversationStatusEnum.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is not active. Start a new session first.",
        )

    service = ConversationService(db)
    return await service.process_turn(session, payload.message)


@router.get(
    "/conversations/{session_id}",
    response_model=list[ConversationMessageRead],
    summary="Historial de sesión",
    description="Devuelve los mensajes de la sesión ordenados por turno. Soporta paginacion con limit/offset.",
)
def get_session_history(
    session_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> list[ConversationMessageRead]:
    _get_session_or_404(session_id, db)
    messages = list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.turn_index, ConversationMessage.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return [ConversationMessageRead.model_validate(m) for m in messages]


@router.get(
    "/users/{user_id}/conversations",
    response_model=list[ConversationSessionRead],
    summary="Lista de sesiones del usuario",
    description="Devuelve las sesiones del usuario ordenadas por actividad reciente.",
)
def list_sessions(
    user_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> list[ConversationSessionRead]:
    _get_user_or_404(user_id, db)
    sessions = list(
        db.scalars(
            select(ConversationSession)
            .where(ConversationSession.user_id == user_id)
            .order_by(ConversationSession.last_activity_at.desc())
            .limit(min(limit, 100))
        ).all()
    )
    return [ConversationSessionRead.model_validate(s) for s in sessions]


@router.get(
    "/users/{user_id}/memories",
    response_model=list[ConversationMemoryRead],
    summary="Memoria persistente del usuario",
    description=(
        "Devuelve los hechos guardados en la memoria persistente de RITA para este usuario. "
        "Por defecto solo devuelve memorias activas. "
        "Útil para el panel de cuidadores para revisar qué sabe RITA sobre la persona."
    ),
)
def get_user_memories(
    user_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: str = Depends(require_frontend_auth),
) -> list[ConversationMemoryRead]:
    _get_user_or_404(user_id, db)
    query = select(ConversationMemory).where(ConversationMemory.user_id == user_id)
    if active_only:
        query = query.where(ConversationMemory.is_active == True)  # noqa: E712
    query = query.order_by(
        ConversationMemory.memory_type,
        ConversationMemory.last_confirmed_at.desc(),
    )
    memories = list(db.scalars(query).all())
    return [ConversationMemoryRead.model_validate(m) for m in memories]
