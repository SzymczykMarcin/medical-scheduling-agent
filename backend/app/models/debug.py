from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.appointment import AppointmentIntent, AppointmentStatus
from app.models.calendar import CalendarEvent
from app.models.rag import RetrievedPassage

DebugStage = Literal["retrieval", "direct_llm", "rag_llm", "validation", "scheduler"]


class AppointmentDebugRequest(BaseModel):
    """Developer request for text-only appointment pipeline diagnostics."""

    transcript: str = Field(min_length=1)
    today: date | None = None


class SchedulerDebugResult(BaseModel):
    """Serializable scheduling result for debug responses."""

    status: AppointmentStatus
    event: CalendarEvent | None
    explanation: str


class AppointmentDebugResponse(BaseModel):
    """Full diagnostic view of the appointment analysis path."""

    status: Literal["completed", "failed"]
    failed_stage: DebugStage | None = None
    error_message: str | None = None
    transcript: str
    direct_bielik_output: str | None = None
    retrieved_context: list[RetrievedPassage] = Field(default_factory=list)
    rag_bielik_raw_output: str | None = None
    validated_intent: AppointmentIntent | None = None
    scheduler_result: SchedulerDebugResult | None = None
    sms_text: str | None = None


class PrewarmComponentResult(BaseModel):
    """One model prewarm result for demo operators."""

    name: str
    status: Literal["ok", "failed"]
    error_message: str | None = None


class PrewarmResponse(BaseModel):
    """Result of loading demo AI components before manual testing."""

    status: Literal["ok", "failed"]
    components: list[PrewarmComponentResult]
