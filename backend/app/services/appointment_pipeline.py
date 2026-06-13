from app.models.appointment import AppointmentIntent, AppointmentResponse
from app.services.asr import TranscriptionService
from app.services.calendar_state import calendar_scheduler
from app.services.exceptions import ServiceError, TranscriptionError
from app.services.rag import RagAnalysisService
from app.services.sms import SmsSimulationService


class AppointmentPipeline:
    """Coordinate ASR, RAG analysis, scheduling and SMS rendering."""

    def __init__(self) -> None:
        self.asr = TranscriptionService()
        self.analyzer = RagAnalysisService()
        self.scheduler = calendar_scheduler
        self.sms = SmsSimulationService()

    def handle_audio_message(self, filename: str, audio: bytes) -> AppointmentResponse:
        """Process one uploaded audio message into an appointment response."""
        transcript = self.asr.transcribe(filename=filename, audio=audio)

        try:
            intent = self.analyzer.analyze(
                transcript=transcript,
                availability_summary=self.scheduler.availability_summary(),
                today=self.scheduler.week_start,
            )
            scheduling_result = self.scheduler.schedule_from_intent(intent)
        except TranscriptionError:
            raise
        except ServiceError as exc:
            intent = self.analyzer_fallback_intent(transcript, str(exc))
            scheduling_result = self.scheduler.callback_result(
                "Automatyczna analiza nie powiodła się; wymagany jest kontakt telefoniczny."
            )

        sms_text = self.sms.render(scheduling_result)
        return AppointmentResponse(
            status=scheduling_result.status,
            transcript=transcript,
            intent=intent,
            event=scheduling_result.event,
            sms_text=sms_text,
            scheduling_explanation=scheduling_result.explanation,
        )

    @staticmethod
    def analyzer_fallback_intent(transcript: str, explanation: str) -> AppointmentIntent:
        """Build a safe callback intent after an expected analysis failure."""
        return AppointmentIntent(
            visit_reason="Wymagane ręczne umówienie wizyty",
            procedure_hint=None,
            preferred_time=None,
            urgency="nieznana",
            duration_minutes=30,
            confidence=0.0,
            requires_human_callback=True,
            explanation=f"{explanation} Transkrypcja: {transcript[:200]}",
        )
