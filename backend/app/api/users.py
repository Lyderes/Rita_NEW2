from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
import uuid
import os
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_frontend_auth
from app.db.session import get_db
from app.models.alert import Alert
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from app.models.user_interpretation_settings import UserInterpretationSettings
from app.models.user_baseline_profile import UserBaselineProfile
from app.models.daily_score import DailyScore
from app.schemas.alert import AlertRead
from app.schemas.baseline import UserBaselineProfileRead, UserBaselineProfileUpdate
from app.schemas.daily_score import DailyScoreRead, DailyScoreHistoryItem
from app.schemas.event import EventRead
from app.schemas.incident import IncidentRead
from app.schemas.overview import UserOverviewRead
from app.schemas.status import UserStatusRead
from app.schemas.timeline import UserTimelineRead
from app.schemas.user import UserCreate, UserRead
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.schemas.user_interpretation_settings import UserInterpretationSettingsRead, UserInterpretationSettingsUpdate
from app.services.daily_score_service import DailyScoringService
from app.services.dashboard_service import build_user_overview
from app.services.status_service import build_user_status
from app.services.gdpr_service import execute_right_to_be_forgotten, UserNotFoundError

router = APIRouter(tags=["users"], dependencies=[Depends(require_frontend_auth)])


@router.post(
    "/users/{user_id}/photo",
    response_model=UserRead,
    summary="Upload user profile photo",
)
async def upload_user_photo(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Ensure dir exists (redundant but safe)
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
        
    # Generate unique filename
    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"user_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join("uploads", filename)
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Update profile_image_url with the static path
    user.profile_image_url = f"/api/v1/uploads/{filename}"
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Creates a monitored user profile. Requires frontend Bearer JWT.",
    responses={
        201: {"description": "User created"},
        401: {"description": "Missing or invalid frontend Bearer token"},
        422: {"description": "Validation error in user payload"},
    },
)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    user = User(
        full_name=payload.full_name,
        birth_date=payload.birth_date,
        notes=payload.notes,
        profile_image_url=payload.profile_image_url,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Update user",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/users/{user_id}/interpretation-settings",
    response_model=UserInterpretationSettingsRead,
    summary="Get user interpretation settings",
)
def get_user_interpretation_settings(
    user_id: int,
    db: Session = Depends(get_db),
) -> UserInterpretationSettings:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return existing or create/persist a default one
    settings = db.scalar(
        select(UserInterpretationSettings).where(UserInterpretationSettings.user_id == user_id)
    )
    if not settings:
        settings = UserInterpretationSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings


@router.put(
    "/users/{user_id}/interpretation-settings",
    response_model=UserInterpretationSettingsRead,
    summary="Update user interpretation settings",
)
def update_user_interpretation_settings(
    user_id: int,
    payload: UserInterpretationSettingsUpdate,
    db: Session = Depends(get_db),
) -> UserInterpretationSettings:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    settings = user.interpretation_settings
    if not settings:
        settings = UserInterpretationSettings(user_id=user_id)
        db.add(settings)
    
    # Update fields
    for field, value in payload.model_dump().items():
        setattr(settings, field, value)
    
    db.commit()
    db.refresh(settings)
    return settings


@router.get(
    "/users",
    response_model=list[UserRead],
    summary="List users",
    description="Returns all users ordered by id. Requires frontend Bearer JWT.",
    responses={401: {"description": "Missing or invalid frontend Bearer token"}},
)
def list_users(db: Session = Depends(get_db)) -> list[User]:
    stmt = select(User).order_by(User.id.asc())
    return list(db.scalars(stmt).all())


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Get user by ID",
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "User not found"},
    },
)
def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get(
    "/users/{user_id}/status",
    response_model=UserStatusRead,
    summary="Get user status",
    description="Returns latest health/status projection for a user. Requires frontend Bearer JWT.",
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "User not found"},
    },
)
def get_user_status(user_id: int, db: Session = Depends(get_db)) -> UserStatusRead:
    status_out = build_user_status(db, user_id)
    if status_out is None:
        raise HTTPException(status_code=404, detail="User not found")
    return status_out


@router.get(
    "/users/{user_id}/timeline",
    response_model=UserTimelineRead,
    summary="Get user timeline",
    description=(
        "Returns recent events, incidents, and alerts for a user. "
        "Requires frontend Bearer JWT."
    ),
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "User not found"},
    },
)
def get_user_timeline(
    user_id: int,
    limit: int = Query(
        default=10,
        ge=1,
        le=200,
        description="Maximum number of recent items returned per section (events, incidents, alerts). Range: 1-200. Default: 10.",
        examples=[10],
    ),
    db: Session = Depends(get_db),
) -> UserTimelineRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    events = list(
        db.scalars(
            select(Event)
            .where(Event.user_id == user_id)
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(limit)
        ).all()
    )
    incidents = list(
        db.scalars(
            select(Incident)
            .where(Incident.user_id == user_id)
            .order_by(Incident.opened_at.desc(), Incident.id.desc())
            .limit(limit)
        ).all()
    )
    alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc(), Alert.id.desc())
            .limit(limit)
        ).all()
    )

    return UserTimelineRead(
        user_id=user.id,
        user_name=user.full_name,
        events=[EventRead.model_validate(event) for event in events],
        incidents=[IncidentRead.model_validate(incident) for incident in incidents],
        alerts=[AlertRead.model_validate(alert) for alert in alerts],
    )


@router.get(
    "/users/{user_id}/baseline",
    response_model=UserBaselineProfileRead,
    summary="Get user baseline profile",
    description="Returns the baseline habits for a user. Returns a default profile if none exists.",
)
def get_user_baseline(user_id: int, db: Session = Depends(get_db)) -> UserBaselineProfile:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    baseline = db.scalar(
        select(UserBaselineProfile).where(UserBaselineProfile.user_id == user_id)
    )
    if not baseline:
        # Create a default one on-the-fly for a consistent frontend experience
        baseline = UserBaselineProfile(user_id=user_id)
        db.add(baseline)
        db.commit()
        db.refresh(baseline)

    return baseline


@router.put(
    "/users/{user_id}/baseline",
    response_model=UserBaselineProfileRead,
    summary="Update user baseline profile",
    description="Updates the baseline habits for a user.",
)
def update_user_baseline(
    user_id: int, payload: UserBaselineProfileUpdate, db: Session = Depends(get_db)
) -> UserBaselineProfile:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    baseline = db.scalar(
        select(UserBaselineProfile).where(UserBaselineProfile.user_id == user_id)
    )
    if not baseline:
        baseline = UserBaselineProfile(user_id=user_id)
        db.add(baseline)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(baseline, field, value)

    db.commit()
    db.refresh(baseline)
    return baseline


@router.get(
    "/users/{user_id}/overview",
    response_model=UserOverviewRead,
    summary="Get user overview",
    description="Returns aggregated user dashboard metrics. Requires frontend Bearer JWT.",
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "User not found"},
    },
)
def get_user_overview(user_id: int, db: Session = Depends(get_db)) -> UserOverviewRead:
    overview = build_user_overview(db, user_id)
    if overview is None:
        raise HTTPException(status_code=404, detail="User not found")
    return overview


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="GDPR Right to be Forgotten",
    description="Permanently deletes a user and all associated data (devices, events, incidents, alerts, jobs) physically in a cascaded transaction.",
    responses={
        401: {"description": "Missing or invalid frontend Bearer token"},
        404: {"description": "User not found"},
    },
)
def delete_user_gdpr(user_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        result = execute_right_to_be_forgotten(db, user_id)
        return result
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/users/{user_id}/daily-score/latest", response_model=DailyScoreRead)
def get_latest_daily_score(user_id: int, db: Session = Depends(get_db)):
    """
    Get the latest daily score for a user.
    If today's score doesn't exist, it attempts to compute it on demand.
    """
    service = DailyScoringService(db)
    # Use explicit date from datetime to avoid shadowing
    import datetime
    today = datetime.date.today()
    
    score = service.get_or_compute_daily_score(user_id, today)
    
    if not score:
        # Try to find the most recent one if today has no activity
        score = db.scalar(
            select(DailyScore)
            .where(DailyScore.user_id == user_id)
            .order_by(DailyScore.date.desc())
            .limit(1)
        )
        
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No hay suficiente actividad para generar una valoración."
        )
    return score


@router.get("/users/{user_id}/daily-score/history", response_model=list[DailyScoreHistoryItem])
def get_daily_score_history(
    user_id: int, 
    limit: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get the history of daily scores for a user.
    """
    stmt = (
        select(DailyScore)
        .where(DailyScore.user_id == user_id)
        .order_by(DailyScore.date.desc())
        .limit(limit)
    )
    scores = db.scalars(stmt).all()
    return scores
