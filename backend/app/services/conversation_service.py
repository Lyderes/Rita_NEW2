"""
ConversationService — orquestador principal del sistema conversacional de RITA.

Flujo por turno:
  1. Cargar perfil del usuario + memoria seleccionada
  2. Recuperar sesión activa (o crear una)
  3. Construir contexto para Claude (PromptBuilder)
  4. Llamar a Claude con retry x1 ante errores transitorios
  5. Persistir turno (user message + assistant message con análisis)
  6. Actualizar sesión (turn_count, follow_up, resumen incremental si toca)
  7. Procesar memoria candidata (MemoryManager)
  8. Evaluar señales con reglas backend → crear evento si corresponde
  9. Si se creó evento → recalcular daily_score del usuario
 10. Expirar memorias antiguas (best-effort)

La lógica crítica (incidentes, alertas, scores) vive en los servicios existentes.
Este servicio sólo decide si disparar esos servicios basándose en reglas propias,
no solo en lo que dice Claude.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.enums import (
    ConversationRoleEnum,
    ConversationStatusEnum,
    EventTypeEnum,
    SeverityEnum,
)
from app.models.conversation_message import ConversationMessage
from app.models.conversation_session import ConversationSession
from app.models.event import Event
from app.models.user import User
from app.models.user_baseline_profile import UserBaselineProfile
from app.models.user_interpretation_settings import UserInterpretationSettings
from app.schemas.conversation import (
    ClaudeConversationOutput,
    ConversationTurnResponse,
    TurnAnalysis,
)
from app.services.ai.conversation_output_parser import parse_claude_output
from app.services.ai.prompt_builder import PromptContext, build_messages_for_claude, get_system_prompt
from app.services.memory_manager import (
    expire_stale_memories,
    process_memory_candidates,
    select_memories_for_context,
)

logger = logging.getLogger(__name__)

# Señales que el backend considera de riesgo medio-alto independientemente de Claude
_BACKEND_HIGH_RISK_SIGNALS = {"fall_risk", "dizziness", "confusion"}
_BACKEND_MEDIUM_RISK_SIGNALS = {"pain", "loneliness", "anxiety", "mobility_issues"}

# Turnos consecutivos con riesgo medio antes de escalar a modelo high-risk
_CONSECUTIVE_MEDIUM_RISK_THRESHOLD = 3

# Códigos HTTP que justifican un retry (solo errores de servidor, nunca 4xx)
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


class ConversationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Gestión de sesiones
    # ------------------------------------------------------------------

    async def get_or_create_session(
        self, user_id: int, force_new: bool = False
    ) -> ConversationSession:
        """Devuelve la sesión activa del usuario o crea una nueva."""
        if not force_new:
            existing = self._get_active_session(user_id)
            if existing is not None:
                if self._is_session_idle(existing):
                    # Cerrar sesión idle con resumen antes de crear una nueva
                    await self._close_session(existing)
                else:
                    return existing

        return self._create_session(user_id)

    def _get_active_session(self, user_id: int) -> ConversationSession | None:
        return self._db.scalar(
            select(ConversationSession).where(
                ConversationSession.user_id == user_id,
                ConversationSession.status == ConversationStatusEnum.active,
            )
        )

    def _is_session_idle(self, session: ConversationSession) -> bool:
        timeout_hours = self._settings.conversation_session_idle_timeout_hours
        last = session.last_activity_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return datetime.now(UTC) - last > timedelta(hours=timeout_hours)

    def _create_session(self, user_id: int) -> ConversationSession:
        session = ConversationSession(
            user_id=user_id,
            status=ConversationStatusEnum.active,
        )
        self._db.add(session)
        self._db.flush()
        logger.info("Created conversation session id=%d for user_id=%d", session.id, user_id)
        return session

    async def _close_session(self, session: ConversationSession) -> None:
        """
        Cierra la sesión.

        FIX #3: Si el resumen incremental está desactualizado (hay turnos desde la
        última actualización), genera un resumen final con el historial completo
        antes de marcar la sesión como ended. Así el resumen que queda en
        session_summary siempre refleja toda la sesión, no sólo los últimos N turnos.
        """
        turns_since_refresh = session.turn_count - session.summary_turn_index
        needs_final_summary = session.turn_count > 0 and turns_since_refresh > 0

        if needs_final_summary:
            all_messages = list(
                self._db.scalars(
                    select(ConversationMessage)
                    .where(ConversationMessage.session_id == session.id)
                    .order_by(ConversationMessage.turn_index, ConversationMessage.id)
                ).all()
            )
            if all_messages:
                await self._refresh_session_summary(
                    session=session,
                    recent_messages=all_messages[:-1],   # todos excepto el último
                    last_user_message="",
                    last_rita_response=all_messages[-1].content if all_messages else "",
                    use_full_history=True,
                )

        session.status = ConversationStatusEnum.ended
        session.ended_at = datetime.now(UTC)
        self._db.add(session)
        logger.info(
            "Closed conversation session id=%d (turns=%d, summary_refreshed=%s)",
            session.id,
            session.turn_count,
            needs_final_summary,
        )

    # ------------------------------------------------------------------
    # Turno principal
    # ------------------------------------------------------------------

    async def process_turn(
        self,
        session: ConversationSession,
        user_message: str,
    ) -> ConversationTurnResponse:
        """
        Procesa un turno completo: guarda el mensaje del usuario, llama a Claude,
        guarda la respuesta y ejecuta todos los efectos secundarios.
        """
        user_id = session.user_id
        turn_index = session.turn_count  # 0-indexed

        # 1. Persistir mensaje del usuario
        user_msg = ConversationMessage(
            session_id=session.id,
            user_id=user_id,
            role=ConversationRoleEnum.user,
            content=user_message,
            turn_index=turn_index,
        )
        self._db.add(user_msg)
        self._db.flush()

        # 2. Cargar contexto
        user = self._db.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        baseline = self._db.scalar(
            select(UserBaselineProfile).where(UserBaselineProfile.user_id == user_id)
        )
        if baseline is None:
            baseline = UserBaselineProfile(user_id=user_id)
            self._db.add(baseline)
            self._db.flush()

        interp_settings = self._db.scalar(
            select(UserInterpretationSettings).where(
                UserInterpretationSettings.user_id == user_id
            )
        )
        if interp_settings is None:
            interp_settings = UserInterpretationSettings(user_id=user_id)
            self._db.add(interp_settings)
            self._db.flush()
        memories = select_memories_for_context(self._db, user_id)
        recent_messages = self._load_recent_messages(session.id, turn_index)
        prev_session_summary = self._get_previous_session_summary(user_id, session.id)

        ctx = PromptContext(
            user=user,
            baseline=baseline,
            settings=interp_settings,
            memories=memories,
            recent_messages=recent_messages,
            session_summary=session.session_summary,
            previous_session_summary=prev_session_summary,
            follow_up_suggestion=session.follow_up_suggestion,
        )

        # 3. Llamar a Claude (con retry x1)
        output = await self._call_claude(ctx, user_message, session)

        # 4. Persistir respuesta del asistente
        analysis = output.analysis
        assistant_msg = ConversationMessage(
            session_id=session.id,
            user_id=user_id,
            role=ConversationRoleEnum.assistant,
            content=output.response,
            turn_index=turn_index,
            mood=analysis.mood if analysis.mood != "unknown" else None,
            risk_level=analysis.risk_level,
            requested_help=analysis.requested_help,
            routine_change_detected=analysis.routine_change_detected,
            raw_analysis_json=analysis.model_dump(),
        )
        self._db.add(assistant_msg)
        self._db.flush()

        # 5. Actualizar sesión
        session.turn_count = turn_index + 1
        session.last_activity_at = datetime.now(UTC)
        session.follow_up_suggestion = analysis.follow_up_suggestion
        self._db.add(session)

        # 6. Resumen incremental si toca
        if self._should_refresh_summary(session):
            await self._refresh_session_summary(
                session, recent_messages, user_message, output.response
            )

        # 7. Procesar memoria
        process_memory_candidates(
            self._db,
            user_id=user_id,
            candidates=analysis.memory_candidates,
            source_session_id=session.id,
            source_message_id=assistant_msg.id,
        )

        # 8. Evaluar señales con reglas backend
        backend_action_taken = self._evaluate_signals_and_act(
            session=session,
            analysis=analysis,
            user_message=user_message,
        )

        # 9. FIX #1: Recalcular daily_score si se creó un evento
        if backend_action_taken:
            self._recompute_daily_score(user_id)

        # 10. Expirar memorias antiguas (best-effort)
        try:
            expire_stale_memories(self._db, user_id)
        except Exception as exc:
            logger.warning("Memory expiration failed (non-critical): %s", exc)

        self._db.commit()

        return ConversationTurnResponse(
            session_id=session.id,
            turn_index=turn_index,
            response=output.response,
            mood=analysis.mood if analysis.mood != "unknown" else None,
            risk_level=analysis.risk_level,
            requested_help=analysis.requested_help,
            backend_action_taken=backend_action_taken,
        )

    # ------------------------------------------------------------------
    # Llamada a Claude (FIX #2: retry x1)
    # ------------------------------------------------------------------

    async def _call_claude(
        self,
        ctx: PromptContext,
        user_message: str,
        session: ConversationSession,
    ) -> ClaudeConversationOutput:
        """
        Llama a Claude y parsea la salida. Nunca lanza excepción al caller.

        FIX #2: Reintenta una vez ante errores transitorios (timeout, 5xx, 429).
        No reintenta errores 4xx que indican un problema en el payload.
        """
        if not self._settings.enable_conversation_ai or not self._settings.anthropic_api_key:
            logger.info("Conversation AI disabled — using fallback response")
            return self._fallback_output()

        model = self._choose_model(session)
        messages = build_messages_for_claude(ctx, user_message)

        headers = {
            "x-api-key": self._settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 1024,
            "system": get_system_prompt(),
            "messages": messages,
        }

        last_exc: Exception | None = None
        for attempt in range(2):  # intento 0 + 1 reintento
            try:
                async with httpx.AsyncClient(
                    timeout=self._settings.conversation_timeout_seconds
                ) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    raw_text = resp.json()["content"][0]["text"]
                    return parse_claude_output(raw_text)

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "Claude timeout (attempt %d/2) on session_id=%d", attempt + 1, session.id
                )
                # Timeout siempre se reintenta
                continue

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status_code = exc.response.status_code
                if status_code in _RETRYABLE_HTTP_CODES:
                    logger.warning(
                        "Claude HTTP %d (attempt %d/2) on session_id=%d — retrying",
                        status_code, attempt + 1, session.id,
                    )
                    continue
                else:
                    # 4xx u otros: no reintentar
                    logger.error(
                        "Claude HTTP %d (non-retryable) on session_id=%d",
                        status_code, session.id,
                    )
                    break

            except Exception as exc:
                last_exc = exc
                logger.error(
                    "Claude unexpected error (attempt %d/2) on session_id=%d: %s",
                    attempt + 1, session.id, exc,
                )
                break

        logger.error(
            "Claude failed after retries on session_id=%d — using fallback. Last error: %s",
            session.id, last_exc,
        )
        return self._fallback_output()

    def _choose_model(self, session: ConversationSession) -> str:
        """
        Usa el modelo de mayor capacidad si hay señales de riesgo en el historial.
        No depende de lo que Claude diga en este turno — lo decide el backend.
        """
        if session.turn_count == 0:
            return self._settings.conversation_model

        recent_risk = list(
            self._db.scalars(
                select(ConversationMessage.risk_level).where(
                    ConversationMessage.session_id == session.id,
                    ConversationMessage.role == ConversationRoleEnum.assistant,
                    ConversationMessage.risk_level.in_(["medium", "high"]),
                ).order_by(ConversationMessage.turn_index.desc()).limit(3)
            ).all()
        )
        if "high" in recent_risk or len(recent_risk) >= _CONSECUTIVE_MEDIUM_RISK_THRESHOLD:
            logger.info("Using high-risk model for session_id=%d", session.id)
            return self._settings.conversation_model_high_risk

        return self._settings.conversation_model

    @staticmethod
    def _fallback_output() -> ClaudeConversationOutput:
        return ClaudeConversationOutput(
            response="Estoy aquí contigo. ¿Puedes contarme un poco más?",
            analysis=TurnAnalysis(),
        )

    # ------------------------------------------------------------------
    # Resumen incremental (ajuste #4 + FIX #3)
    # ------------------------------------------------------------------

    def _should_refresh_summary(self, session: ConversationSession) -> bool:
        refresh_every = self._settings.conversation_summary_refresh_every_n_turns
        turns_since_refresh = session.turn_count - session.summary_turn_index
        return turns_since_refresh >= refresh_every

    async def _refresh_session_summary(
        self,
        session: ConversationSession,
        recent_messages: list[ConversationMessage],
        last_user_message: str,
        last_rita_response: str,
        use_full_history: bool = False,
    ) -> None:
        """
        Pide a Claude un resumen breve de la sesión.

        use_full_history=True se usa al cerrar la sesión: incluye todos los mensajes
        disponibles en lugar de sólo los recientes. Así el resumen final es completo.
        """
        if not self._settings.enable_conversation_ai or not self._settings.anthropic_api_key:
            return

        history_lines = [
            f"{'Persona' if m.role == 'user' else 'RITA'}: {m.content}"
            for m in recent_messages
        ]
        if not use_full_history and last_user_message:
            history_lines.append(f"Persona: {last_user_message}")
            history_lines.append(f"RITA: {last_rita_response}")

        if not history_lines:
            return

        history_text = "\n".join(history_lines)
        prompt = (
            "Resume en 2-3 frases lo más importante de esta conversación entre RITA y "
            "la persona usuaria. Incluye: estado emocional, temas tratados y cualquier "
            f"hecho relevante mencionado.\n\n{history_text}"
        )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._settings.conversation_model,
                        "max_tokens": 200,
                        "system": "Eres un asistente que resume conversaciones de forma concisa.",
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                summary = resp.json()["content"][0]["text"].strip()
                session.session_summary = summary
                session.summary_turn_index = session.turn_count
                self._db.add(session)
                logger.debug(
                    "Session summary refreshed for session_id=%d (full=%s)",
                    session.id, use_full_history,
                )
        except Exception as exc:
            logger.warning("Session summary refresh failed (non-critical): %s", exc)

    # ------------------------------------------------------------------
    # Evaluación de señales con reglas backend
    # ------------------------------------------------------------------

    def _evaluate_signals_and_act(
        self,
        session: ConversationSession,
        analysis: TurnAnalysis,
        user_message: str,
    ) -> bool:
        """
        Aplica reglas backend para decidir si crear un evento.
        NO confía ciegamente en risk_level de Claude.
        Returns True si se creó al menos un evento.
        """
        signals = set(analysis.signals)
        backend_action = False

        if analysis.requested_help:
            self._create_conversation_event(
                session=session,
                event_type=EventTypeEnum.assistance_needed,
                severity=SeverityEnum.high,
                user_text=user_message,
                analysis=analysis,
            )
            backend_action = True
            logger.info("Backend action: requested_help on session_id=%d", session.id)

        elif _BACKEND_HIGH_RISK_SIGNALS & signals:
            if analysis.risk_level in ("medium", "high"):
                # Doble confirmación: señal de riesgo + Claude también lo detecta
                self._create_conversation_event(
                    session=session,
                    event_type=EventTypeEnum.health_concern,
                    severity=SeverityEnum.high if analysis.risk_level == "high" else SeverityEnum.medium,
                    user_text=user_message,
                    analysis=analysis,
                )
                backend_action = True
                logger.info(
                    "Backend action: high-risk signals %s on session_id=%d",
                    _BACKEND_HIGH_RISK_SIGNALS & signals,
                    session.id,
                )

        elif _BACKEND_MEDIUM_RISK_SIGNALS & signals and analysis.risk_level == "high":
            self._create_conversation_event(
                session=session,
                event_type=EventTypeEnum.wellbeing_check_failed,
                severity=SeverityEnum.medium,
                user_text=user_message,
                analysis=analysis,
            )
            backend_action = True

        return backend_action

    def _get_user_device_id(self, user_id: int) -> int | None:
        from app.models.device import Device
        device = self._db.scalar(
            select(Device).where(Device.user_id == user_id, Device.is_active == True)  # noqa: E712
        ) or self._db.scalar(
            select(Device).where(Device.user_id == user_id)
        )
        return device.id if device else None

    def _create_conversation_event(
        self,
        session: ConversationSession,
        event_type: EventTypeEnum,
        severity: SeverityEnum,
        user_text: str | None,
        analysis: TurnAnalysis,
    ) -> Event:
        device_id = self._get_user_device_id(session.user_id)
        event = Event(
            trace_id=str(uuid.uuid4()),
            user_id=session.user_id,
            device_id=device_id,
            event_type=event_type,
            severity=severity,
            source="conversation",
            user_text=user_text,
            payload_json={
                "session_id": session.id,
                "signals": analysis.signals,
                "mood": analysis.mood,
                "risk_level": analysis.risk_level,
                "requested_help": analysis.requested_help,
                "summary": analysis.summary,
                "source": "conversation_service",
            },
        )
        self._db.add(event)
        self._db.flush()  # Necesitamos created_at para daily_score
        logger.info(
            "Created event type=%s severity=%s from conversation session_id=%d",
            event_type.value, severity.value, session.id,
        )
        return event

    # ------------------------------------------------------------------
    # Daily score recomputation
    # ------------------------------------------------------------------

    def _recompute_daily_score(self, user_id: int) -> None:
        """
        Recalcula el daily score del día actual para que las señales detectadas
        en la conversación se reflejen en el dashboard del cuidador.

        Mismo patrón que check_in_analysis_service.py.
        """
        try:
            from app.services.daily_score_service import DailyScoringService
            DailyScoringService(self._db).compute_daily_score(
                user_id, datetime.now(UTC).date()
            )
            logger.debug("Daily score recomputed for user_id=%d", user_id)
        except Exception as exc:
            logger.error(
                "Daily score recomputation failed for user_id=%d (non-critical): %s",
                user_id, exc,
            )

    # ------------------------------------------------------------------
    # Helpers de carga
    # ------------------------------------------------------------------

    def _load_recent_messages(
        self, session_id: int, current_turn_index: int
    ) -> list[ConversationMessage]:
        max_turns = self._settings.conversation_max_turns_in_context
        return list(
            self._db.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == session_id,
                    ConversationMessage.turn_index < current_turn_index,
                )
                .order_by(ConversationMessage.turn_index.desc())
                .limit(max_turns)
            ).all()
        )[::-1]

    def _get_previous_session_summary(
        self, user_id: int, current_session_id: int
    ) -> str | None:
        prev = self._db.scalar(
            select(ConversationSession)
            .where(
                ConversationSession.user_id == user_id,
                ConversationSession.id != current_session_id,
                ConversationSession.session_summary.is_not(None),
            )
            .order_by(ConversationSession.last_activity_at.desc())
        )
        return prev.session_summary if prev else None
