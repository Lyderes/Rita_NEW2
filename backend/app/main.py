from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os

from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.dashboard import router as dashboard_router
from app.api.devices import router as devices_router
from app.api.events import router as events_router
from app.api.incidents import router as incidents_router
from app.api.metrics import router as metrics_router
from app.api.reminders import router as reminders_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging_config import configure_logging
from app.core.rate_limit import limiter
from app.core.background_workers import (
    AlertEscalationWorker,
    DataRetentionWorker,
    HeartbeatMonitorWorker,
    MqttWorker,
    NotificationWorker,
)
from app.db.session import SessionLocal

from app.api.deps import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.middleware import RequestIDMiddleware
from fastapi.responses import RedirectResponse

settings = get_settings()

configure_logging(debug=settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    workers = [
        MqttWorker(session_factory=SessionLocal),
        NotificationWorker(
            session_factory=SessionLocal,
            interval_seconds=60,
            batch_size=100,
            base_backoff_seconds=30,
        ),
        AlertEscalationWorker(
            session_factory=SessionLocal,
            interval_seconds=60,
            pending_threshold_minutes=10,
        ),
        HeartbeatMonitorWorker(
            session_factory=SessionLocal,
            interval_seconds=60,
            offline_threshold_minutes=30,
            no_heartbeat_grace_minutes=30,
        ),
        DataRetentionWorker(session_factory=SessionLocal),
    ]
    for worker in workers:
        worker.start()
    try:
        yield
    finally:
        for worker in reversed(workers):
            worker.stop()


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version="0.1.0",
    description=(
        "RITA backend API. Authentication modes:\n"
        "- Frontend endpoints require Bearer JWT obtained from /auth/login.\n"
        "- Edge ingestion endpoints require X-Device-Token.\n"
        "Errors follow a common envelope with error, message, code, and request_id."
    ),
    openapi_tags=[
        {"name": "health", "description": "Service liveness and version checks."},
        {"name": "auth", "description": "Frontend authentication (JWT issuance)."},
        {"name": "dashboard", "description": "Global dashboard projections and KPIs."},
        {"name": "users", "description": "User CRUD and per-user projections."},
        {"name": "devices", "description": "Device provisioning, status, and token lifecycle."},
        {"name": "events", "description": "Event ingestion and event querying."},
        {"name": "incidents", "description": "Incident query and state transitions."},
        {"name": "alerts", "description": "Alert query and state transitions."},
        {"name": "metrics", "description": "Internal observability counters and latency snapshots."},
        {"name": "conversations", "description": "Sistema conversacional con memoria persistente."},
    ],
)

# Middleware — registration order in Starlette: add_middleware inserts at
# position 0 each time, so the LAST call added is OUTERMOST (first to see
# the request).  Concretely here:
#   incoming → CORSMiddleware → RequestIDMiddleware → ExceptionMiddleware → StaticFiles → routes
#
# Static files for profile pictures
uploads_dir = "uploads"
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)
app.mount("/api/v1/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# RequestIDMiddleware is intentionally placed INSIDE CORSMiddleware and
# OUTSIDE ExceptionMiddleware (which runs our registered error handlers).
# This guarantees request.state.request_id is set before any route handler
# or error handler executes.
app.add_middleware(RequestIDMiddleware)

# Use explicit origins because allow_credentials=True is incompatible with "*"
cors_allowed_origins = settings.allowed_origins
if settings.debug or settings.allow_all_origins:
    # If debug is on, we'll allow all but still need to be explicit for credentials
    # For local dev, we include common ones
    cors_allowed_origins = list(set(cors_allowed_origins + ["http://localhost:5190", "http://127.0.0.1:5190", "http://localhost:5300", "http://127.0.0.1:5300", "http://localhost:8080", "http://127.0.0.1:8080"]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter — state must be set before middleware is added.
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Global exception handlers — replace FastAPI defaults with our envelope.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    description="Returns API status and version.",
)
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
        
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "app": settings.app_name, 
        "version": "0.1.0"
    }


app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)
app.include_router(reminders_router)
app.include_router(users_router)
app.include_router(devices_router)
app.include_router(events_router)
app.include_router(incidents_router)
app.include_router(alerts_router)
app.include_router(metrics_router)


@app.get("/", include_in_schema=False)
def root():
    """Redirige a la documentación interactiva."""
    return RedirectResponse(url="/docs")
