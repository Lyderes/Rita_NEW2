"""
Tests para memory_manager.py

Cubre:
  - _word_overlap_ratio: idéntico, sin solapamiento, parcial
  - select_memories_for_context: prioridad por tipo, límite, solo activas
  - process_memory_candidates: crear nueva, deduplicar, filtrar confianza baja,
    escalar confianza, respetar límite máximo
  - expire_stale_memories: expirar por TTL, no tocar memorias sin TTL
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.conversation_memory import ConversationMemory
from app.models.conversation_session import ConversationSession
from app.models.conversation_message import ConversationMessage
from app.domain.enums import ConversationRoleEnum, ConversationStatusEnum, MemoryTypeEnum
from app.schemas.conversation import MemoryCandidate
from app.services.memory_manager import (
    _word_overlap_ratio,
    expire_stale_memories,
    process_memory_candidates,
    select_memories_for_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(
    db: Session,
    user_id: int,
    memory_type: str,
    content: str,
    confidence: str = "high",
    is_active: bool = True,
    last_confirmed_offset_days: int = 0,
    expires_after_days: int | None = None,
) -> ConversationMemory:
    last_confirmed = datetime.now(UTC) - timedelta(days=last_confirmed_offset_days)
    mem = ConversationMemory(
        user_id=user_id,
        memory_type=memory_type,
        content=content,
        confidence=confidence,
        is_active=is_active,
        last_confirmed_at=last_confirmed,
        expires_after_days=expires_after_days,
    )
    db.add(mem)
    db.flush()
    return mem


def _make_session(db: Session, user_id: int) -> ConversationSession:
    session = ConversationSession(
        user_id=user_id,
        status=ConversationStatusEnum.active,
    )
    db.add(session)
    db.flush()
    return session


def _make_message(db: Session, session_id: int, user_id: int, content: str = "test") -> ConversationMessage:
    msg = ConversationMessage(
        session_id=session_id,
        user_id=user_id,
        role=ConversationRoleEnum.user,
        content=content,
        turn_index=0,
    )
    db.add(msg)
    db.flush()
    return msg


# ---------------------------------------------------------------------------
# _word_overlap_ratio
# ---------------------------------------------------------------------------

def test_word_overlap_identical():
    ratio = _word_overlap_ratio("me duele la rodilla", "me duele la rodilla")
    assert ratio == 1.0


def test_word_overlap_no_overlap():
    ratio = _word_overlap_ratio("me duele la rodilla", "le gusta el café")
    assert ratio == 0.0


def test_word_overlap_partial():
    ratio = _word_overlap_ratio("me duele la rodilla izquierda", "me duele la cadera")
    assert 0 < ratio < 1


def test_word_overlap_empty_strings():
    assert _word_overlap_ratio("", "algo") == 0.0
    assert _word_overlap_ratio("algo", "") == 0.0


# ---------------------------------------------------------------------------
# select_memories_for_context
# ---------------------------------------------------------------------------

def test_select_memories_priority_order(db_session: Session):
    user = db_session.get(__import__('app.models.user', fromlist=['User']).User, 1)
    user_id = user.id

    _make_memory(db_session, user_id, "routine", "Pasea a las 9", last_confirmed_offset_days=5)
    _make_memory(db_session, user_id, "health", "Tiene diabetes", last_confirmed_offset_days=2)
    _make_memory(db_session, user_id, "person", "Se llama María", last_confirmed_offset_days=10)
    _make_memory(db_session, user_id, "preference", "Le gusta el café", last_confirmed_offset_days=3)
    db_session.commit()

    memories = select_memories_for_context(db_session, user_id)
    types = [m.memory_type for m in memories]

    # person y preference deben ir antes que health y routine
    assert types.index("person") < types.index("health")
    assert types.index("preference") < types.index("routine")


def test_select_memories_excludes_inactive(db_session: Session):
    user_id = 1
    _make_memory(db_session, user_id, "person", "Memoria activa", is_active=True)
    _make_memory(db_session, user_id, "person", "Memoria inactiva", is_active=False)
    db_session.commit()

    memories = select_memories_for_context(db_session, user_id)
    contents = [m.content for m in memories]
    assert "Memoria activa" in contents
    assert "Memoria inactiva" not in contents


def test_select_memories_respects_limit(db_session: Session):
    user_id = 1
    for i in range(10):
        _make_memory(db_session, user_id, "preference", f"Preferencia {i}")
    db_session.commit()

    memories = select_memories_for_context(db_session, user_id, max_items=3)
    assert len(memories) <= 3


# ---------------------------------------------------------------------------
# process_memory_candidates
# ---------------------------------------------------------------------------

def test_process_creates_new_memory(db_session: Session):
    user_id = 1
    session = _make_session(db_session, user_id)
    msg = _make_message(db_session, session.id, user_id)
    db_session.commit()

    candidates = [
        MemoryCandidate(type="person", content="Se llama Antonio", confidence="high"),
    ]
    created = process_memory_candidates(db_session, user_id, candidates, session.id, msg.id)
    db_session.commit()

    assert created == 1
    mems = db_session.scalars(
        __import__('sqlalchemy', fromlist=['select']).select(ConversationMemory).where(
            ConversationMemory.user_id == user_id
        )
    ).all()
    assert any(m.content == "Se llama Antonio" for m in mems)


def test_process_skips_low_confidence(db_session: Session):
    user_id = 1
    session = _make_session(db_session, user_id)
    msg = _make_message(db_session, session.id, user_id)
    db_session.commit()

    candidates = [
        MemoryCandidate(type="health", content="Quizás tiene artritis", confidence="low"),
    ]
    created = process_memory_candidates(db_session, user_id, candidates, session.id, msg.id)
    db_session.commit()

    assert created == 0


def test_process_deduplicates_similar_content(db_session: Session):
    user_id = 1
    session = _make_session(db_session, user_id)
    msg = _make_message(db_session, session.id, user_id)

    # Crear memoria existente
    existing = _make_memory(db_session, user_id, "health", "le duele la rodilla derecha")
    db_session.commit()

    original_mention_count = existing.mention_count or 0

    # Candidato muy similar
    candidates = [
        MemoryCandidate(type="health", content="le duele la rodilla derecha bastante", confidence="high"),
    ]
    created = process_memory_candidates(db_session, user_id, candidates, session.id, msg.id)
    db_session.commit()

    # No debe crear nueva memoria — solo actualizar
    assert created == 0
    db_session.refresh(existing)
    assert (existing.mention_count or 0) > original_mention_count


def test_process_creates_new_for_different_content(db_session: Session):
    user_id = 1
    session = _make_session(db_session, user_id)
    msg = _make_message(db_session, session.id, user_id)

    _make_memory(db_session, user_id, "health", "tiene diabetes tipo 2")
    db_session.commit()

    candidates = [
        MemoryCandidate(type="health", content="le duele la espalda lumbar", confidence="high"),
    ]
    created = process_memory_candidates(db_session, user_id, candidates, session.id, msg.id)
    db_session.commit()

    assert created == 1


def test_process_escalates_confidence_to_high(db_session: Session):
    user_id = 1
    session = _make_session(db_session, user_id)
    msg = _make_message(db_session, session.id, user_id)

    existing = _make_memory(db_session, user_id, "person", "se llama juan", confidence="medium")
    db_session.commit()

    candidates = [
        MemoryCandidate(type="person", content="se llama juan", confidence="high"),
    ]
    process_memory_candidates(db_session, user_id, candidates, session.id, msg.id)
    db_session.commit()

    db_session.refresh(existing)
    assert existing.confidence == "high"


def test_process_enforces_memory_limit(db_session: Session):
    from app.core.config import get_settings
    settings = get_settings()
    max_active = settings.conversation_memory_max_active

    user_id = 1
    session = _make_session(db_session, user_id)
    msg = _make_message(db_session, session.id, user_id)

    # Llenar hasta el límite
    for i in range(max_active):
        _make_memory(
            db_session, user_id, "preference", f"preferencia numero {i}",
            last_confirmed_offset_days=max_active - i,  # más reciente = índice más alto
        )
    db_session.commit()

    # Añadir uno más
    candidates = [
        MemoryCandidate(type="person", content="nombre completamente nuevo distinto", confidence="high"),
    ]
    process_memory_candidates(db_session, user_id, candidates, session.id, msg.id)
    db_session.commit()

    from sqlalchemy import select, func
    active_count = db_session.scalar(
        select(func.count()).select_from(
            select(ConversationMemory).where(
                ConversationMemory.user_id == user_id,
                ConversationMemory.is_active == True,
            ).subquery()
        )
    )
    assert active_count <= max_active


# ---------------------------------------------------------------------------
# expire_stale_memories
# ---------------------------------------------------------------------------

def test_expire_old_emotional_memory(db_session: Session):
    user_id = 1
    # emotional TTL es 30 días — creamos una de 40 días
    old_mem = _make_memory(
        db_session, user_id, "emotional", "se sentía triste",
        last_confirmed_offset_days=40,
        expires_after_days=30,
    )
    db_session.commit()

    expired = expire_stale_memories(db_session, user_id)
    db_session.commit()

    assert expired >= 1
    db_session.refresh(old_mem)
    assert old_mem.is_active is False


def test_no_expire_recent_memory(db_session: Session):
    user_id = 1
    recent_mem = _make_memory(
        db_session, user_id, "emotional", "se sentía contenta hoy",
        last_confirmed_offset_days=5,
        expires_after_days=30,
    )
    db_session.commit()

    expired = expire_stale_memories(db_session, user_id)
    db_session.commit()

    assert expired == 0
    db_session.refresh(recent_mem)
    assert recent_mem.is_active is True


def test_no_expire_memory_without_ttl(db_session: Session):
    user_id = 1
    permanent_mem = _make_memory(
        db_session, user_id, "person", "se llama María",
        last_confirmed_offset_days=500,
        expires_after_days=None,  # sin TTL → nunca expira
    )
    db_session.commit()

    expired = expire_stale_memories(db_session, user_id)
    db_session.commit()

    assert expired == 0
    db_session.refresh(permanent_mem)
    assert permanent_mem.is_active is True


def test_expire_returns_correct_count(db_session: Session):
    user_id = 1
    for i in range(3):
        _make_memory(
            db_session, user_id, "routine", f"rutina vieja {i}",
            last_confirmed_offset_days=100,
            expires_after_days=90,
        )
    _make_memory(
        db_session, user_id, "routine", "rutina reciente",
        last_confirmed_offset_days=10,
        expires_after_days=90,
    )
    db_session.commit()

    expired = expire_stale_memories(db_session, user_id)
    assert expired == 3
