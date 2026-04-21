from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_frontend_auth
from app.db.session import get_db
from app.schemas.dashboard import DashboardRead
from app.services.dashboard_service import build_dashboard_summary

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_frontend_auth)])


@router.get(
    "/dashboard",
    response_model=DashboardRead,
    summary="Get dashboard summary",
    description="Returns global KPIs for dashboard cards. Requires frontend Bearer JWT.",
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardRead:
    return build_dashboard_summary(db)