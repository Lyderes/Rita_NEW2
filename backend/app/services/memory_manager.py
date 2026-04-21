"""
MemoryManager — gestión selectiva de la memoria persistente de RITA.

Responsabilidades:
  1. Seleccionar qué memorias inyectar en cada turno (relevance selector).
  2. Procesar los memory_candidates que propone Claude:
     - Deduplicación por tipo + contenido normalizado (ajuste #3)
     - Persistir solo si confidence >= medium
     - Actualizar last_confirmed_at si ya existe algo similar
  3. Expirar memorias antiguas que no se han confirmado (ajuste #7).
  4. Controlar el límite máximo de memorias activas por usuario (ajuste #5).

No toma decisiones de negocio críticas — eso es responsabilidad del
ConversationService y del pipeline de eventos existente.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.enums import MemoryConfidenceEnum, MemoryTypeEnum
from app.models.conversation_memory import MEMORY_TTL_BY_TYPE, ConversationMemory
from app.schemas.conversation import MemoryCandidate

logger = logging.getLogger(__name__)

# Confidence mínima para persistir un candidato de memoria
_MIN_PERSISTENCE_CONFIDENCE = {
    MemoryConfidenceEnum.high.value,
    MemoryConfidenceEnum.medium.value,
}

# Similarity threshold para considerar dos memorias como duplicadas.
# Si el contenido normalizado comparte >= este ratio de palabras, se fusionan.
_DUPLICATE_WORD_OVERLAP_THRESHOLD = 0.6


def _normalize_text(text: str) -> str:
    """Normaliza texto para comparación: minúsculas, sin puntuación extra."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _word_overlap_ratio(a: str, b: str) -> float:
    """Ratio de palabras compartidas sobre el total de palabras únicas."""
    words_a = set(_normalize_text(a).split())
    words_b = set(_normalize_text(b).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _is_duplicate(candidate_content: str, existing: ConversationMemory) -> bool:
    """Determina si un candidato es suficientemente similar a una memoria existente."""
    ratio = _word_overlap_ratio(candidate_content, existing.content)
    return ratio >= _DUPLICATE_WORD_OVERLAP_THRESHOLD


# ---------------------------------------------------------------------------
# Relevance Selector (ajuste #5)
# ---------------------------------------------------------------------------

def select_memories_for_context(
    db: Session,
    user_id: int,
    max_items: int | None = None,
) -> list[ConversationMemory]:
    """
    Selecciona las memorias más relevantes para inyectar en el contexto.

    Estrategia de priorización (no embeddings — prioridad por tipo y recencia):
      1. Personas y preferencias — estables, siempre útiles
      2. Salud confirmada recientemente
      3. Rutinas confirmadas recientemente
      4. Estado emocional reciente
      5. Eventos de vida

    Dentro de cada grupo: ordena por last_confirmed_at DESC.
    """
    settings = get_settings()
    limit = max_items or settings.conversation_memory_max_items

    all_active = list(
        db.scalars(
            select(ConversationMemory)
            .where(
                ConversationMemory.user_id == user_id,
                ConversationMemory.is_active == True,  # noqa: E712
            )
            .order_by(ConversationMemory.last_confirmed_at.desc())
        ).all()
    )

    # Prioridad por tipo
    priority: dict[str, int] = {
        MemoryTypeEnum.person.value: 0,
        MemoryTypeEnum.preference.value: 1,
        MemoryTypeEnum.health.value: 2,
        MemoryTypeEnum.routine.value: 3,
        MemoryTypeEnum.emotional.value: 4,
        MemoryTypeEnum.life_event.value: 5,
    }

    sorted_memories = sorted(
        all_active,
        key=lambda m: (
            priority.get(m.memory_type, 99),
            # Más recientemente confirmada primero dentro del mismo tipo
            -(m.last_confirmed_at.timestamp() if m.last_confirmed_at else 0),
        ),
    )

    return sorted_memories[:limit]


# ---------------------------------------------------------------------------
# Procesamiento de candidatos
# ---------------------------------------------------------------------------

def process_memory_candidates(
    db: Session,
    user_id: int,
    candidates: list[MemoryCandidate],
    source_session_id: int,
    source_message_id: int,
) -> int:
    """
    Procesa los memory_candidates propuestos por Claude.

    Returns:
        Número de memorias nuevas creadas.
    """
    if not candidates:
        return 0

    settings = get_settings()
    created = 0

    for candidate in candidates:
        # Filtrar confianza baja
        if candidate.confidence not in _MIN_PERSISTENCE_CONFIDENCE:
            logger.debug(
                "Skipping low-confidence memory candidate (type=%s, confidence=%s)",
                candidate.type,
                candidate.confidence,
            )
            continue

        # Validar tipo de memoria
        valid_types = {e.value for e in MemoryTypeEnum}
        if candidate.type not in valid_types:
            logger.warning("Unknown memory type '%s' — skipping", candidate.type)
            continue

        content = candidate.content.strip()
        if not content:
            continue

        # Buscar memorias existentes del mismo tipo para deduplicar
        existing_of_type = list(
            db.scalars(
                select(ConversationMemory).where(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.memory_type == candidate.type,
                    ConversationMemory.is_active == True,  # noqa: E712
                )
            ).all()
        )

        duplicate = next(
            (m for m in existing_of_type if _is_duplicate(content, m)), None
        )

        if duplicate is not None:
            # Actualizar la memoria existente en lugar de crear una nueva
            duplicate.last_confirmed_at = datetime.now(UTC)
            duplicate.mention_count = (duplicate.mention_count or 0) + 1
            # Escalar confianza si antes era medium y ahora es high
            if (
                candidate.confidence == MemoryConfidenceEnum.high.value
                and duplicate.confidence != MemoryConfidenceEnum.high.value
            ):
                duplicate.confidence = MemoryConfidenceEnum.high.value
            db.add(duplicate)
            logger.debug("Updated existing memory id=%d (type=%s)", duplicate.id, candidate.type)
            continue

        # Crear nueva memoria
        ttl = MEMORY_TTL_BY_TYPE.get(candidate.type)
        new_memory = ConversationMemory(
            user_id=user_id,
            memory_type=candidate.type,
            content=content,
            confidence=candidate.confidence,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
            expires_after_days=ttl,
        )
        db.add(new_memory)
        created += 1
        logger.debug("Created new memory (type=%s, confidence=%s)", candidate.type, candidate.confidence)

    # Aplicar límite máximo de memorias activas (desactivar las más antiguas).
    # Flush primero para que las memorias recién creadas sean visibles en la consulta.
    if created > 0:
        db.flush()
    _enforce_memory_limit(db, user_id, settings.conversation_memory_max_active)

    return created


def _enforce_memory_limit(db: Session, user_id: int, max_active: int) -> None:
    """Desactiva las memorias más antiguas si se supera el límite."""
    all_active = list(
        db.scalars(
            select(ConversationMemory)
            .where(
                ConversationMemory.user_id == user_id,
                ConversationMemory.is_active == True,  # noqa: E712
            )
            .order_by(ConversationMemory.last_confirmed_at.desc())
        ).all()
    )

    if len(all_active) <= max_active:
        return

    to_deactivate = all_active[max_active:]
    for mem in to_deactivate:
        mem.is_active = False
        db.add(mem)
    logger.info(
        "Memory limit enforced for user_id=%d: deactivated %d memories",
        user_id,
        len(to_deactivate),
    )


# ---------------------------------------------------------------------------
# Expiración de memorias (ajuste #7)
# ---------------------------------------------------------------------------

def expire_stale_memories(db: Session, user_id: int) -> int:
    """
    Desactiva memorias que no se han confirmado en más tiempo del permitido.

    Política por tipo (definida en MEMORY_TTL_BY_TYPE):
      - person: nunca expira
      - routine: 90 días
      - health: 60 días
      - emotional: 30 días
      - preference: nunca expira
      - life_event: nunca expira

    Returns:
        Número de memorias desactivadas.
    """
    now = datetime.now(UTC)
    expired_count = 0

    active_with_ttl = list(
        db.scalars(
            select(ConversationMemory).where(
                ConversationMemory.user_id == user_id,
                ConversationMemory.is_active == True,  # noqa: E712
                ConversationMemory.expires_after_days != None,  # noqa: E711
            )
        ).all()
    )

    for mem in active_with_ttl:
        if mem.expires_after_days is None:
            continue
        last_confirmed = mem.last_confirmed_at
        if last_confirmed.tzinfo is None:
            last_confirmed = last_confirmed.replace(tzinfo=UTC)
        cutoff = now - timedelta(days=mem.expires_after_days)
        if last_confirmed < cutoff:
            mem.is_active = False
            db.add(mem)
            expired_count += 1
            logger.debug(
                "Expired memory id=%d (type=%s, last_confirmed=%s)",
                mem.id,
                mem.memory_type,
                mem.last_confirmed_at.date(),
            )

    if expired_count:
        logger.info(
            "Expired %d stale memories for user_id=%d", expired_count, user_id
        )

    return expired_count
