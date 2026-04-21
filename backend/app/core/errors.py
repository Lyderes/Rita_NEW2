from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import REQUEST_ID_HEADER

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error response schema
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Consistent error envelope returned by every error handler.

    Fields
    ------
    error:      Short machine-readable error type (e.g. "not_found").
    message:    Human-readable description, safe to surface to front-end.
    code:       HTTP status code repeated in the body for easy client parsing.
    request_id: Echoed from ``request.state.request_id`` when available.
    """

    error: str
    message: str
    code: int
    request_id: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_TO_ERROR: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    503: "service_unavailable",
    500: "internal_server_error",
}


def _error_type(status_code: int) -> str:
    return _STATUS_TO_ERROR.get(status_code, "error")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle FastAPI/Starlette HTTPException with the consistent error envelope."""
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    body = ErrorResponse(
        error=_error_type(exc.status_code),
        message=detail,
        code=exc.status_code,
        request_id=_request_id(request),
    )
    headers: dict[str, str] = {}
    # Preserve WWW-Authenticate header for 401 responses (RFC 7235).
    if exc.status_code == 401 and exc.headers:
        www_auth = exc.headers.get("WWW-Authenticate")
        if www_auth:
            headers["WWW-Authenticate"] = www_auth

    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
        headers=headers if headers else None,
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic / FastAPI request validation errors (422)."""
    assert isinstance(exc, RequestValidationError)
    # Flatten validation errors into a readable summary without exposing internal paths.
    first_error = exc.errors()[0] if exc.errors() else {}
    loc = " -> ".join(str(p) for p in first_error.get("loc", []))
    msg = first_error.get("msg", "Validation error")
    summary = f"{loc}: {msg}" if loc else str(msg)

    body = ErrorResponse(
        error="validation_error",
        message=summary,
        code=422,
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=422, content=body.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected server errors.

    Logs the full traceback at ERROR level (with request_id for correlation)
    but returns a generic 500 to the client — no internal details leak.

    This handler runs inside ServerErrorMiddleware, which is *outermost*.  That
    means RequestIDMiddleware's post-processing (setting the response header) is
    bypassed for unhandled exceptions, so we set X-Request-ID explicitly here.
    """
    rid = _request_id(request)
    logger.exception(
        "Unhandled exception request_id=%s method=%s path=%s",
        rid,
        request.method,
        request.url.path,
        exc_info=exc,
    )
    body = ErrorResponse(
        error="internal_server_error",
        message="An unexpected error occurred. Please try again later.",
        code=500,
        request_id=rid,
    )
    response = JSONResponse(status_code=500, content=body.model_dump())
    # Set the header explicitly: for unhandled exceptions the response exits via
    # ServerErrorMiddleware, bypassing RequestIDMiddleware's header injection.
    if rid:
        response.headers[REQUEST_ID_HEADER] = rid
    return response
