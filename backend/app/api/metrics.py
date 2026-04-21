from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_frontend_auth
from app.services.metrics_service import get_metrics_snapshot

router = APIRouter(tags=["metrics"], dependencies=[Depends(require_frontend_auth)])


@router.get(
    "/metrics/summary",
    summary="Get internal metrics summary",
    description=(
        "Returns in-memory counters and HTTP latency snapshots for internal observability. "
        "Protected with frontend Bearer JWT to avoid exposing operational internals publicly."
    ),
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def metrics_summary() -> dict[str, object]:
    return get_metrics_snapshot()
