from datetime import datetime

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    id: str
    patient_label: str
    title: str
    start: datetime
    end: datetime
    duration_minutes: int
    status: str = "scheduled"
