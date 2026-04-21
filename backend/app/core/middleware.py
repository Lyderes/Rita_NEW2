from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.services.metrics_service import increment_http_request, observe_http_duration

REQUEST_ID_HEADER = "X-Request-ID"

# Headers that must NEVER appear in logs under any circumstances.
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "x-device-token",
        "cookie",
        "set-cookie",
    }
)

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to every request/response cycle.

    If the incoming request already carries ``X-Request-ID`` the value is
    re-used; otherwise a new UUID4 is generated.  The id is:

    * stored in ``request.state.request_id`` for use anywhere in the app
    * echoed back in the response header ``X-Request-ID``
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: object) -> Response:  # type: ignore[override]
        from collections.abc import Awaitable, Callable

        _call_next: Callable[[Request], Awaitable[Response]] = call_next  # type: ignore[assignment]

        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and incoming.strip() else str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.monotonic()
        response: Response = await _call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        response.headers[REQUEST_ID_HEADER] = request_id

        endpoint = _resolve_endpoint(request)
        increment_http_request(request.method, endpoint, response.status_code)
        observe_http_duration(endpoint, duration_ms)

        _log_request(request, response.status_code, duration_ms, request_id, endpoint)

        return response


def _log_request(
    request: Request,
    status_code: int,
    duration_ms: float,
    request_id: str,
    endpoint: str,
) -> None:
    """Emit a single structured log line per request.

    Deliberately avoids logging:
    - Authorization header values
    - X-Device-Token values
    - Cookie values
    - Any request body
    """
    # Log level based on status code for easy filtering.
    if status_code >= 500:
        log = logger.error
    elif status_code >= 400:
        log = logger.warning
    else:
        log = logger.info

    log(
        "request method=%s path=%s endpoint=%s status=%d duration_ms=%s request_id=%s",
        request.method,
        request.url.path,
        endpoint,
        status_code,
        duration_ms,
        request_id,
    )


def _resolve_endpoint(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path
