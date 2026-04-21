from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.check_in_analysis import CheckInAnalysis
from app.models.event import Event
from app.services.ai.claude_client import ClaudeClient
from app.schemas.check_in_analysis import CheckInAnalysisCreate

from app.services.ai.rule_based_analysis import normalize_analysis, run_rule_based_analysis

logger = logging.getLogger(__name__)

class CheckInAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.client = ClaudeClient()
        self.settings = get_settings()

    async def analyze_event_check_in(self, event: Event) -> CheckInAnalysis | None:
        """
        Analyze a check-in event's text using AI and persist the result.
        Strictly enforces the Phase 1 hardening contract.
        """
        # 1. Input normalization
        user_text = event.payload_json.get("user_text") or event.payload_json.get("transcript") or event.user_text
        if not user_text or not str(user_text).strip():
            logger.info(f"Event {event.id} has no text to analyze. Skipping.")
            return None

        text_str = str(user_text).strip()
        raw_analysis = None
        model_used = "rule-based-fallback"

        # 2. AI Analysis path
        if self.settings.enable_checkin_ai_analysis:
            system_prompt = (
                "Eres un asistente especializado en el cuidado de personas mayores (RITA).\n"
                "Analiza el texto y devuelve un JSON con este formato EXACTO:\n"
                "{\n"
                "  \"summary\": \"resumen de 1 frase\",\n"
                "  \"mood\": \"positive\" | \"neutral\" | \"low\" | \"unknown\",\n"
                "  \"signals\": [\"lista\", \"de\", \"señales\"],\n"
                "  \"risk\": \"low\" | \"medium\" | \"high\"\n"
                "}\n"
                "Usa 'signals' en inglés (ej. pain, dizziness, lonely, fall, urgency, hunger)."
            )

            try:
                logger.info(f"Starting AI analysis for event {event.id}...")
                raw_analysis = await self.client.analyze_text(system_prompt, text_str)
                model_used = self.settings.anthropic_model
            except Exception as e:
                logger.error(f"AI analysis failed for event {event.id}: {e}")

        # 3. Fallback path
        if not raw_analysis:
            raw_analysis = run_rule_based_analysis(text_str)
            logger.info(f"Using rule-based fallback for event {event.id}")

        # 4. Normalization Layer (Hardening)
        normalized = normalize_analysis(raw_analysis)

        try:
            # 5. Persistence with new contract
            analysis_data = CheckInAnalysisCreate(
                event_id=event.id,
                text=text_str,
                summary=normalized["summary"],
                mood=normalized["mood"],
                signals=normalized["signals"],
                risk=normalized["risk"],
                model_used=model_used,
                raw_response=raw_analysis
            )
            
            db_analysis = CheckInAnalysis(**analysis_data.model_dump())
            self.db.add(db_analysis)
            self.db.commit()
            self.db.refresh(db_analysis)
            
            logger.info(f"Check-in Analysis hardened and persisted for event {event.id} with risk: {db_analysis.risk}")
            
            # Trigger daily score recompute
            try:
                self.db.refresh(event) # Ensure created_at is populated
                from app.services.daily_score_service import DailyScoringService
                scoring_service = DailyScoringService(self.db)
                scoring_service.compute_daily_score(event.user_id, event.created_at.date())
                logger.debug(f"Daily score recomputed for user {event.user_id} on {event.created_at.date()}")
            except Exception as e:
                logger.error(f"Failed to recompute daily score for user {event.user_id}: {str(e)}")
            
            return db_analysis
            
        except Exception as e:
            logger.error(f"Failed to persist check-in analysis for event {event.id}: {str(e)}")
            self.db.rollback()
            return None
