from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa para los modelos ORM."""


def register_models() -> None:
    """Importa los modelos para registrarlos en Base.metadata."""
    from app.models.alert import Alert  # noqa: F401
    from app.models.audit_log import AuditLog  # noqa: F401
    from app.models.device import Device  # noqa: F401
    from app.models.event import Event  # noqa: F401
    from app.models.frontend_user import FrontendUser  # noqa: F401
    from app.models.incident import Incident  # noqa: F401
    from app.models.notification_job import NotificationJob  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.check_in_analysis import CheckInAnalysis  # noqa: F401
    from app.models.user_baseline_profile import UserBaselineProfile
    from app.models.user_interpretation_settings import UserInterpretationSettings
    from app.models.scheduled_reminder import ScheduledReminder # noqa: F401
    from app.models.daily_score import DailyScore  # noqa: F401
    from app.models.conversation_session import ConversationSession  # noqa: F401
    from app.models.conversation_message import ConversationMessage  # noqa: F401
    from app.models.conversation_memory import ConversationMemory  # noqa: F401
