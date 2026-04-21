from __future__ import annotations

import logging
import sys


def configure_logging(debug: bool = False) -> None:
    """Configure root logging for the application.

    Uses a plain text format suitable for local development and structured
    enough to be parseable in production logs. Does NOT emit any credential
    or auth-related fields — callers are responsible for sanitising log
    messages before passing them here.
    """
    level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if called more than once (e.g. in tests).
    if root.handlers:
        root.handlers.clear()
    root.addHandler(handler)

    # Reduce noise from libraries that are too chatty at DEBUG.
    # sqlalchemy.engine: would otherwise log every SQL statement at INFO.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # uvicorn.access: suppressed because RequestIDMiddleware already emits one
    # structured log line per request (method/path/status/duration_ms/request_id).
    # Keeping both would produce duplicate per-request lines.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # httpx / httpcore: used by Starlette's TestClient in the test suite;
    # their per-request client logs are noise alongside our server-side logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
