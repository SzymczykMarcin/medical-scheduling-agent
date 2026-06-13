from fastapi import APIRouter

from app.models.calendar import CalendarEvent
from app.services.calendar_state import calendar_scheduler

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events", response_model=list[CalendarEvent])
def list_events() -> list[CalendarEvent]:
    return calendar_scheduler.list_events()
