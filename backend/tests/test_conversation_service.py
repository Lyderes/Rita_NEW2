"""
Tests para ConversationService

Estrategia: se mockea _call_claude para no depender de la API de Anthropic.
Los tests cubren:
  - get_or_create_session: crear nueva, reusar activa, cerrar sesión idle
  - _is_session_idle: umbral de inactividad
  - _choose_model: modelo por defecto vs escalado por riesgo
  - _evaluate_signals_and_act: reglas backend (requested_help, high-risk, medium-risk)
  - process_turn: flujo completo con Claude mockeado
  - Fallback cuando AI está deshabilitada
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.domain.enums import ConversationRoleEnum, ConversationStatusEnum
from app.models.conversation_message import ConversationMessage
from app.models.conversation_session import ConversationSession
from app.schemas.conversation import ClaudeConversationOutput, TurnAnalysis
from app.services.conversation_service import ConversationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(db: Session) -> ConversationService:
    return ConversationService(db)


def _fallback_output(
    response: str = "Estoy aquí contigo.",
    mood: str = "neutral",
    risk_level: str = "low",
    requested_help: bool = False,
    signals: list[str] | None = None,
) -> ClaudeConversationOutput:
    return ClaudeConversationOutput(
        response=response,
        analysis=TurnAnalysis(
            mood=mood,
            risk_level=risk_level,
            requested_help=requested_help,
            signals=signals or [],
        ),
    )


def _get_user_id(db: Session) -> int:
    from app.models.user import User
    user = db.scalars(__import__('sqlalchemy', fromlist=['select']).select(User)).first()
    assert user is not None, "conftest should seed a user"
    return user.id


# ---------------------------------------------------------------------------
# get_or_create_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creates_new_session(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)

    session = await service.get_or_create_session(user_id)
    db_session.commit()

    assert session.user_id == user_id
    assert session.status == ConversationStatusEnum.active
    assert session.id is not None


@pytest.mark.asyncio
async def test_reuses_active_session(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)

    session1 = await service.get_or_create_session(user_id)
    db_session.commit()

    session2 = await service.get_or_create_session(user_id)
    assert session1.id == session2.id


@pytest.mark.asyncio
async def test_force_new_creates_new_session(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)

    session1 = await service.get_or_create_session(user_id)
    db_session.commit()

    session2 = await service.get_or_create_session(user_id, force_new=True)
    db_session.commit()

    assert session2.id != session1.id
    assert session2.status == ConversationStatusEnum.active


@pytest.mark.asyncio
async def test_idle_session_is_closed_and_new_created(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)

    # Crear sesión y hacerla idle manualmente
    session1 = await service.get_or_create_session(user_id)
    session1.last_activity_at = datetime.now(UTC) - timedelta(hours=25)
    db_session.add(session1)
    db_session.commit()

    # Mockear _close_session para no llamar a Claude en el cierre
    with patch.object(service, '_close_session', new_callable=AsyncMock) as mock_close:
        session2 = await service.get_or_create_session(user_id)
        db_session.commit()

    mock_close.assert_called_once_with(session1)
    assert session2.id != session1.id
    assert session2.status == ConversationStatusEnum.active


# ---------------------------------------------------------------------------
# _is_session_idle
# ---------------------------------------------------------------------------

def test_session_not_idle_recently_active(db_session: Session):
    service = _make_service(db_session)
    session = ConversationSession(
        user_id=1,
        status=ConversationStatusEnum.active,
        last_activity_at=datetime.now(UTC) - timedelta(hours=1),
    )
    assert service._is_session_idle(session) is False


def test_session_is_idle_after_timeout(db_session: Session):
    service = _make_service(db_session)
    timeout = service._settings.conversation_session_idle_timeout_hours
    session = ConversationSession(
        user_id=1,
        status=ConversationStatusEnum.active,
        last_activity_at=datetime.now(UTC) - timedelta(hours=timeout + 1),
    )
    assert service._is_session_idle(session) is True


# ---------------------------------------------------------------------------
# _choose_model
# ---------------------------------------------------------------------------

def test_choose_model_default_for_new_session(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active, turn_count=0)
    db_session.add(session)
    db_session.flush()

    model = service._choose_model(session)
    assert model == service._settings.conversation_model


def test_choose_model_escalates_on_high_risk(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active, turn_count=3)
    db_session.add(session)
    db_session.flush()

    # Crear mensajes de asistente con riesgo alto
    db_session.add(ConversationMessage(
        session_id=session.id,
        user_id=user_id,
        role=ConversationRoleEnum.assistant,
        content="Hay riesgo",
        turn_index=0,
        risk_level="high",
    ))
    db_session.flush()

    model = service._choose_model(session)
    assert model == service._settings.conversation_model_high_risk


def test_choose_model_escalates_on_three_consecutive_medium(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active, turn_count=3)
    db_session.add(session)
    db_session.flush()

    for i in range(3):
        db_session.add(ConversationMessage(
            session_id=session.id,
            user_id=user_id,
            role=ConversationRoleEnum.assistant,
            content="Hay algo",
            turn_index=i,
            risk_level="medium",
        ))
    db_session.flush()

    model = service._choose_model(session)
    assert model == service._settings.conversation_model_high_risk


# ---------------------------------------------------------------------------
# _evaluate_signals_and_act
# ---------------------------------------------------------------------------

def test_evaluate_requested_help_creates_event(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    analysis = TurnAnalysis(requested_help=True, risk_level="high", signals=[])
    acted = service._evaluate_signals_and_act(session, analysis, "Necesito ayuda")
    db_session.flush()

    assert acted is True


def test_evaluate_high_risk_signal_with_claude_agreement_creates_event(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    analysis = TurnAnalysis(
        requested_help=False,
        risk_level="high",
        signals=["fall_risk"],
    )
    acted = service._evaluate_signals_and_act(session, analysis, "Me caí")
    db_session.flush()

    assert acted is True


def test_evaluate_high_risk_signal_without_claude_agreement_no_event(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    # fall_risk en señales pero Claude dice riesgo bajo → no actúa (doble confirmación)
    analysis = TurnAnalysis(
        requested_help=False,
        risk_level="low",
        signals=["fall_risk"],
    )
    acted = service._evaluate_signals_and_act(session, analysis, "Tuve un susto")
    db_session.flush()

    assert acted is False


def test_evaluate_no_signals_no_action(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    analysis = TurnAnalysis(requested_help=False, risk_level="low", signals=[])
    acted = service._evaluate_signals_and_act(session, analysis, "Estoy bien")

    assert acted is False


# ---------------------------------------------------------------------------
# process_turn (Claude mockeado)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_turn_persists_messages(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    with patch.object(service, '_call_claude', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = _fallback_output("Qué buenas noticias.")
        result = await service.process_turn(session, "Hoy me encuentro bien")

    assert result.response == "Qué buenas noticias."
    assert result.turn_index == 0

    from sqlalchemy import select
    messages = list(db_session.scalars(
        select(ConversationMessage).where(ConversationMessage.session_id == session.id)
    ).all())
    assert len(messages) == 2  # user + assistant
    roles = {m.role for m in messages}
    assert ConversationRoleEnum.user in roles
    assert ConversationRoleEnum.assistant in roles


@pytest.mark.asyncio
async def test_process_turn_increments_turn_count(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    with patch.object(service, '_call_claude', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = _fallback_output()
        await service.process_turn(session, "Primer mensaje")

    assert session.turn_count == 1


@pytest.mark.asyncio
async def test_process_turn_uses_fallback_when_ai_disabled(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    # Deshabilitar IA en settings
    original = service._settings.enable_conversation_ai
    object.__setattr__(service._settings, 'enable_conversation_ai', False)
    try:
        result = await service.process_turn(session, "Hola")
    finally:
        object.__setattr__(service._settings, 'enable_conversation_ai', original)

    assert result.response  # tiene respuesta de fallback
    assert result.backend_action_taken is False


@pytest.mark.asyncio
async def test_process_turn_backend_action_on_requested_help(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    with patch.object(service, '_call_claude', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = _fallback_output(
            response="Entiendo, aviso a tu cuidador.",
            requested_help=True,
            risk_level="high",
        )
        result = await service.process_turn(session, "Necesito ayuda, me caí")

    assert result.backend_action_taken is True
    assert result.requested_help is True


@pytest.mark.asyncio
async def test_process_turn_auto_creates_baseline_and_settings(db_session: Session):
    """process_turn debe crear UserBaselineProfile y UserInterpretationSettings
    con defaults si no existen, para que Claude siempre tenga contexto completo."""
    from sqlalchemy import select
    from app.models.user_baseline_profile import UserBaselineProfile
    from app.models.user_interpretation_settings import UserInterpretationSettings

    service = _make_service(db_session)
    user_id = _get_user_id(db_session)

    # Verificar que no existen previamente
    assert db_session.scalar(select(UserBaselineProfile).where(UserBaselineProfile.user_id == user_id)) is None
    assert db_session.scalar(select(UserInterpretationSettings).where(UserInterpretationSettings.user_id == user_id)) is None

    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    with patch.object(service, '_call_claude', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = _fallback_output("Hola, ¿cómo estás?")
        await service.process_turn(session, "Buenos días")

    # Ahora deben existir con valores por defecto
    baseline = db_session.scalar(select(UserBaselineProfile).where(UserBaselineProfile.user_id == user_id))
    settings = db_session.scalar(select(UserInterpretationSettings).where(UserInterpretationSettings.user_id == user_id))
    assert baseline is not None
    assert settings is not None


@pytest.mark.asyncio
async def test_process_turn_second_turn_uses_context(db_session: Session):
    service = _make_service(db_session)
    user_id = _get_user_id(db_session)
    session = ConversationSession(user_id=user_id, status=ConversationStatusEnum.active)
    db_session.add(session)
    db_session.flush()

    with patch.object(service, '_call_claude', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = _fallback_output("Hola.")
        await service.process_turn(session, "Primer turno")

        mock_claude.return_value = _fallback_output("Segundo turno OK.")
        result = await service.process_turn(session, "Segundo turno")

    assert result.turn_index == 1
    assert session.turn_count == 2
