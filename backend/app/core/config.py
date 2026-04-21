from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5180",
    "http://127.0.0.1:5180",
    "http://localhost:5190",
    "http://127.0.0.1:5190",
]

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _normalize_database_url(raw_value: str) -> str:
    if not raw_value.startswith("sqlite:///"):
        return raw_value

    sqlite_path = raw_value.removeprefix("sqlite:///")
    if sqlite_path == ":memory:" or sqlite_path.startswith("/"):
        return raw_value

    resolved = (BACKEND_ROOT / sqlite_path).resolve()
    return f"sqlite:///{resolved.as_posix()}"


def _parse_allowed_origins(raw_value: str | list[str] | None) -> list[str]:
    default_origins = DEFAULT_ALLOWED_ORIGINS
    if raw_value is None:
        return default_origins

    if isinstance(raw_value, list):
        origins = [str(origin).strip() for origin in raw_value if str(origin).strip()]
    else:
        if not raw_value.strip():
            return default_origins
        origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]

    if not origins:
        return default_origins
    if len(origins) == 1 and origins[0] == "*":
        return ["*"]
    if "*" in origins:
        raise ValueError("ALLOWED_ORIGINS cannot mix '*' with specific origins")

    deduped: list[str] = []
    for origin in origins:
        if origin not in deduped:
            deduped.append(origin)
    return deduped


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,
    )

    app_name: str = Field(default="RITA Backend")
    debug: bool = Field(default=False)
    backend_host: str = Field(default="localhost", validation_alias=AliasChoices("BACKEND_HOST"))
    backend_port: int = Field(default=8080, validation_alias=AliasChoices("BACKEND_PORT"))
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5434/rita")
    jwt_secret: str = Field(
        default="rita-local-secret-key-change-me-2026",
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY"),
    )
    access_token_expire_minutes: int = Field(default=60)
    auto_provision_edge_devices: bool = Field(default=False)
    allowed_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_ALLOWED_ORIGINS))
    allow_all_origins: bool = Field(default=False)
    frontend_username: str = Field(default="admin")
    frontend_password: str = Field(default="change-me-in-env")
    
    # Notifications Configuration
    fcm_credentials_path: str | None = Field(default=None)
    twilio_account_sid: str | None = Field(default=None)
    twilio_auth_token: str | None = Field(default=None)
    twilio_phone_number: str | None = Field(default=None)
    
    # GDPR & Data Retention
    enable_data_retention: bool = Field(default=False)
    data_retention_events_days: int = Field(default=90)
    data_retention_notification_jobs_days: int = Field(default=30)
    data_retention_closed_alerts_days: int = Field(default=180)
    
    # Anthropic / Claude
    # Anthropic / Claude — análisis de check-in
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")
    anthropic_timeout_seconds: int = Field(default=30)
    enable_checkin_ai_analysis: bool = Field(default=False)

    # Anthropic / Claude — sistema conversacional
    enable_conversation_ai: bool = Field(default=False)
    # Modelo para turnos normales (Haiku es suficiente y más barato)
    conversation_model: str = Field(default="claude-haiku-4-5-20251001")
    # Modelo para turnos con riesgo detectado (no solo por Claude)
    conversation_model_high_risk: str = Field(default="claude-sonnet-4-6")
    conversation_timeout_seconds: int = Field(default=15)
    # Número de turnos recientes que se incluyen en el contexto de cada llamada
    conversation_max_turns_in_context: int = Field(default=8)
    # Número máximo de memorias persistentes inyectadas en cada turno
    conversation_memory_max_items: int = Field(default=15)
    # Cada cuántos turnos se regenera el resumen incremental de sesión
    conversation_summary_refresh_every_n_turns: int = Field(default=6)
    # Horas de inactividad antes de cerrar automáticamente una sesión
    conversation_session_idle_timeout_hours: int = Field(default=4)
    # Máximo de memorias activas por usuario
    conversation_memory_max_active: int = Field(default=50)

    @property
    def secret_key(self) -> str:
        # Backward-compatible alias used by existing security code.
        # Stripping just in case there are hidden whitespace/newlines from .env
        return self.jwt_secret.strip()

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _validate_allowed_origins(cls, value: str | list[str] | None) -> list[str]:
        return _parse_allowed_origins(value)

    @field_validator("database_url", mode="before")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        return _normalize_database_url(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
