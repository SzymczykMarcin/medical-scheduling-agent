from datetime import date

from app.models.appointment import AppointmentIntent
from app.services.appointment_pipeline import AppointmentPipeline
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError
from app.services.scheduler import SchedulerService
from app.services.sms import SmsSimulationService


class FakeAsr:
    """ASR test double returning a deterministic Polish transcript."""

    def transcribe(self, filename: str, audio: bytes) -> str:
        return "Prosze o wizyte we wtorek po 10."


class SuccessfulAnalyzer:
    """Analyzer test double capturing pipeline inputs for contract checks."""

    def __init__(self) -> None:
        self.transcript: str | None = None
        self.availability_summary: str | None = None
        self.today: date | None = None

    def analyze(self, transcript: str, availability_summary: str, today: date) -> AppointmentIntent:
        self.transcript = transcript
        self.availability_summary = availability_summary
        self.today = today
        return AppointmentIntent(
            visit_reason="Ból gardła",
            procedure_hint="Konsultacja POZ",
            preferred_days=["2026-06-09"],
            urgency="standardowa",
            duration_minutes=30,
            confidence=0.9,
            explanation="Pacjent poprosił o wtorek.",
        )


class InvalidJsonAnalyzer:
    """Analyzer test double simulating malformed LLM output."""

    def analyze(self, transcript: str, availability_summary: str, today: date) -> AppointmentIntent:
        raise RagAnalysisError("Invalid JSON.")


class MissingRagAnalyzer:
    """Analyzer test double simulating a missing vector index."""

    def analyze(self, transcript: str, availability_summary: str, today: date) -> AppointmentIntent:
        raise RagDataNotReadyError("RAG vector store is not ready.")


def build_pipeline(analyzer) -> AppointmentPipeline:
    pipeline = AppointmentPipeline()
    pipeline.asr = FakeAsr()
    pipeline.analyzer = analyzer
    pipeline.scheduler = SchedulerService(today=date(2026, 6, 12))
    pipeline.sms = SmsSimulationService()
    return pipeline


def test_pipeline_schedules_when_rag_analysis_is_clear() -> None:
    analyzer = SuccessfulAnalyzer()

    response = build_pipeline(analyzer).handle_audio_message(
        filename="patient.webm",
        audio=b"audio",
    )

    assert response.status == "scheduled"
    assert response.event is not None
    assert response.event.start.isoformat() == "2026-06-09T09:00:00"
    assert "Wizyta została umówiona" in response.sms_text
    assert analyzer.transcript == "Prosze o wizyte we wtorek po 10."
    assert analyzer.today == date(2026, 6, 8)
    assert analyzer.availability_summary is not None
    assert "2026-06-09" in analyzer.availability_summary


def test_pipeline_returns_callback_when_rag_analysis_fails() -> None:
    response = build_pipeline(InvalidJsonAnalyzer()).handle_audio_message(
        filename="patient.webm",
        audio=b"audio",
    )

    assert response.status == "needs_callback"
    assert response.event is None
    assert response.intent.requires_human_callback is True
    assert "skontaktuje się telefonicznie" in response.sms_text


def test_pipeline_returns_callback_when_rag_index_is_missing() -> None:
    response = build_pipeline(MissingRagAnalyzer()).handle_audio_message(
        filename="patient.webm",
        audio=b"audio",
    )

    assert response.status == "needs_callback"
    assert response.event is None
    assert response.intent.requires_human_callback is True
    assert "kontakt telefoniczny" in response.scheduling_explanation
