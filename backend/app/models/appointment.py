from typing import Literal

from pydantic import BaseModel, Field

from app.models.calendar import CalendarEvent

AppointmentStatus = Literal["scheduled", "needs_callback", "failed"]


class PreferredTimeWindow(BaseModel):
    """One preferred appointment time window extracted from speech."""

    date: str | None = Field(default=None, description="ISO date, YYYY-MM-DD, when known.")
    start_time: str | None = Field(default=None, description="24h HH:MM lower bound.")
    end_time: str | None = Field(default=None, description="24h HH:MM upper bound.")


class AppointmentIntent(BaseModel):
    """Structured appointment request extracted from a transcript."""

    visit_reason: str
    procedure_hint: str | None = None
    preferred_time: str | None = None
    preferred_days: list[str] = Field(default_factory=list)
    preferred_time_windows: list[PreferredTimeWindow] = Field(default_factory=list)
    excluded_days: list[str] = Field(default_factory=list)
    specific_datetime: str | None = Field(default=None, description="ISO datetime when explicitly requested.")
    urgency: str = Field(description="Scheduling urgency, not a medical diagnosis.")
    duration_minutes: int
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_human_callback: bool = False
    explanation: str


class AppointmentResponse(BaseModel):
    """Response returned after processing a voice appointment request."""

    status: AppointmentStatus
    transcript: str
    intent: AppointmentIntent
    event: CalendarEvent | None
    sms_text: str
    scheduling_explanation: str
