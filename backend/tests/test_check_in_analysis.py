from __future__ import annotations

import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session
from app.models.event import Event
from app.models.check_in_analysis import CheckInAnalysis
from app.services.check_in_analysis_service import CheckInAnalysisService
from app.domain.enums import EventTypeEnum, SeverityEnum
import uuid

@pytest.fixture
def mock_claude_response():
    return {
        "summary": "El usuario se encuentra bien pero un poco solo.",
        "risk": "low",
        "signals": ["lonely"],
        "recommended_action": "Llamada de seguimiento por la tarde."
    }

@pytest.mark.asyncio
async def test_check_in_analysis_service_success(db_session: Session, mock_claude_response, monkeypatch):
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("ENABLE_CHECKIN_AI_ANALYSIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    
    # Create a dummy event
    event = Event(
        trace_id=str(uuid.uuid4()),
        user_id=1, # assuming seed data from fixture or manual
        device_id=1,
        event_type=EventTypeEnum.checkin,
        severity=SeverityEnum.low,
        source="test",
        payload_json={"user_text": "Hola, estoy bien, gracias por preguntar."}
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    
    service = CheckInAnalysisService(db_session)
    
    with patch("app.services.ai.claude_client.ClaudeClient.analyze_text") as mock_analyze:
        mock_analyze.return_value = mock_claude_response
        
        analysis = await service.analyze_event_check_in(event)
        
        assert analysis is not None
        assert analysis.risk == "low"
        assert analysis.summary == mock_claude_response["summary"]
        assert "lonely" in analysis.signals
        
        # Verify persistence
        db_analysis = db_session.get(CheckInAnalysis, analysis.id)
        assert db_analysis is not None
        assert db_analysis.event_id == event.id

@pytest.mark.asyncio
async def test_check_in_analysis_service_disabled(db_session: Session, monkeypatch):
    monkeypatch.setenv("ENABLE_CHECKIN_AI_ANALYSIS", "false")
    
    event = Event(
        trace_id=str(uuid.uuid4()),
        user_id=1,
        device_id=1,
        event_type=EventTypeEnum.checkin,
        severity=SeverityEnum.low,
        source="test",
        payload_json={"user_text": "ignore me"}
    )
    db_session.add(event)
    db_session.commit()
    
    service = CheckInAnalysisService(db_session)
    # With hardening, it falls back to rule-based analysis even if AI is disabled
    analysis = await service.analyze_event_check_in(event)
    assert analysis is not None
    assert analysis.risk == "low"
    assert "Check-in rutinario" in analysis.summary

@pytest.mark.asyncio
async def test_check_in_analysis_service_error_handling(db_session: Session, monkeypatch):
    monkeypatch.setenv("ENABLE_CHECKIN_AI_ANALYSIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    
    event = Event(
        trace_id=str(uuid.uuid4()),
        user_id=1,
        device_id=1,
        event_type=EventTypeEnum.checkin,
        severity=SeverityEnum.low,
        source="test",
        payload_json={"user_text": "Hola"}
    )
    db_session.add(event)
    db_session.commit()
    
    service = CheckInAnalysisService(db_session)
    
    with patch("app.services.ai.claude_client.ClaudeClient.analyze_text") as mock_analyze:
        mock_analyze.side_effect = Exception("Anthropic API Error")
        
        # Should not return None, but fall back to rule-based analysis
        analysis = await service.analyze_event_check_in(event)
        assert analysis is not None
        assert analysis.risk == "low"
        assert analysis.model_used == "rule-based-fallback"
