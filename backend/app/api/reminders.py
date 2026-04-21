from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_frontend_auth
from app.db.session import get_db
from app.models.user import User
from app.models.scheduled_reminder import ScheduledReminder
from app.schemas.scheduled_reminder import ScheduledReminderCreate, ScheduledReminderRead, ScheduledReminderUpdate

router = APIRouter(tags=["reminders"])


@router.get(
    "/users/{user_id}/reminders",
    response_model=list[ScheduledReminderRead],
    summary="List all reminders for a user",
)
def list_reminders(
    user_id: int,
    db: Session = Depends(get_db),
    _token: str = Depends(require_frontend_auth),
) -> list[ScheduledReminder]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return list(user.reminders)


@router.post(
    "/users/{user_id}/reminders",
    response_model=ScheduledReminderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new reminder",
)
def create_reminder(
    user_id: int,
    payload: ScheduledReminderCreate,
    db: Session = Depends(get_db),
    _token: str = Depends(require_frontend_auth),
) -> ScheduledReminder:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    reminder = ScheduledReminder(
        user_id=user_id,
        **payload.model_dump()
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.put(
    "/reminders/{reminder_id}",
    response_model=ScheduledReminderRead,
    summary="Update an existing reminder",
)
def update_reminder(
    reminder_id: int,
    payload: ScheduledReminderUpdate,
    db: Session = Depends(get_db),
    _token: str = Depends(require_frontend_auth),
) -> ScheduledReminder:
    reminder = db.get(ScheduledReminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reminder, field, value)
    
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete(
    "/reminders/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reminder",
)
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    _token: str = Depends(require_frontend_auth),
):
    reminder = db.get(ScheduledReminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    db.delete(reminder)
    db.commit()
    return
