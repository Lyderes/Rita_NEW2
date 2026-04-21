from pydantic import BaseModel

from app.schemas.alert import AlertRead
from app.schemas.event import EventRead
from app.schemas.incident import IncidentRead


class UserTimelineRead(BaseModel):
    user_id: int
    user_name: str
    events: list[EventRead]
    incidents: list[IncidentRead]
    alerts: list[AlertRead]
