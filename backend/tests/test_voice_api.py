from fastapi.testclient import TestClient

from app.api import voice
from app.main import app
from app.models.appointment import AppointmentIntent, AppointmentResponse
from app.models.calendar import CalendarEvent
from app.services.exceptions import AudioValidationError


class FakeTranscriptionService:
    def transcribe(self, filename: str, audio: bytes) -> str:
        assert filename == "patient.webm"
        assert audio == b"audio-bytes"
        return "Pacjent prosi o termin wizyty."


def test_transcription_endpoint_returns_transcript(monkeypatch) -> None:
    monkeypatch.setattr(voice, "transcription_service", FakeTranscriptionService())
    client = TestClient(app)

    response = client.post(
        "/api/voice/transcriptions",
        files={"audio": ("patient.webm", b"audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "filename": "patient.webm",
        "transcript": "Pacjent prosi o termin wizyty.",
    }


def test_transcription_endpoint_returns_bad_request_for_invalid_audio(monkeypatch) -> None:
    class RejectingTranscriptionService:
        def transcribe(self, filename: str, audio: bytes) -> str:
            raise AudioValidationError("Uploaded audio is empty.")

    monkeypatch.setattr(voice, "transcription_service", RejectingTranscriptionService())
    client = TestClient(app)

    response = client.post(
        "/api/voice/transcriptions",
        files={"audio": ("empty.webm", b"", "audio/webm")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded audio is empty."}


def test_appointments_endpoint_returns_scheduled_response(monkeypatch) -> None:
    class SchedulingPipeline:
        def handle_audio_message(self, filename: str, audio: bytes) -> AppointmentResponse:
            assert filename == "patient.webm"
            assert audio == b"audio-bytes"
            return AppointmentResponse(
                status="scheduled",
                transcript="Prosze o wizyte we wtorek po 10.",
                intent=AppointmentIntent(
                    visit_reason="Sore throat",
                    procedure_hint="GP consultation",
                    preferred_days=["2026-06-09"],
                    urgency="standard",
                    duration_minutes=30,
                    confidence=0.9,
                    explanation="Tuesday after 10.",
                ),
                event=CalendarEvent(
                    id="new-1",
                    patient_label="Demo patient",
                    title="Sore throat",
                    start="2026-06-09T10:30:00",
                    end="2026-06-09T11:00:00",
                    duration_minutes=30,
                ),
                sms_text="Wizyta zostala umowiona.",
                scheduling_explanation="Appointment booked.",
            )

    monkeypatch.setattr(voice, "pipeline", SchedulingPipeline())
    client = TestClient(app)

    response = client.post(
        "/api/voice/appointments",
        files={"audio": ("patient.webm", b"audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "scheduled"
    assert response.json()["event"]["id"] == "new-1"


def test_appointments_endpoint_returns_callback_response(monkeypatch) -> None:
    class CallbackPipeline:
        def handle_audio_message(self, filename: str, audio: bytes) -> AppointmentResponse:
            return AppointmentResponse(
                status="needs_callback",
                transcript="Nie wiem kiedy moge przyjsc.",
                intent=AppointmentIntent(
                    visit_reason="Manual scheduling required",
                    urgency="unknown",
                    duration_minutes=30,
                    confidence=0.0,
                    requires_human_callback=True,
                    explanation="Unclear request.",
                ),
                event=None,
                sms_text="Pracownik placowki skontaktuje sie telefonicznie.",
                scheduling_explanation="No matching free calendar slot was found.",
            )

    monkeypatch.setattr(voice, "pipeline", CallbackPipeline())
    client = TestClient(app)

    response = client.post(
        "/api/voice/appointments",
        files={"audio": ("patient.webm", b"audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_callback"
    assert response.json()["event"] is None
