import logging
from datetime import date
from typing import Protocol

from app.core.settings import Settings, get_settings
from app.models.debug import AppointmentDebugResponse, SchedulerDebugResult
from app.models.rag import ConversationMessage, RetrievedPassage
from app.services.exceptions import RagAnalysisError, ServiceError
from app.services.intent_postprocessing import apply_polish_weekday_sanity_checks
from app.services.rag import _parse_appointment_intent
from app.services.rag_prompting import SchedulingPromptBuilder
from app.services.rag_retrieval import create_knowledge_base_retriever
from app.services.scheduler import SchedulerService
from app.services.sms import SmsSimulationService

logger = logging.getLogger(__name__)


class RetrieverProtocol(Protocol):
    """Interface for debug RAG retrieval."""

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Retrieve RAG passages."""


class LlmProtocol(Protocol):
    """Interface for debug LLM generation."""

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate text from chat messages."""


class AppointmentDebugAnalysisService:
    """Run a text-only direct-vs-RAG appointment diagnostic flow."""

    def __init__(
        self,
        settings: Settings | None = None,
        retriever: RetrieverProtocol | None = None,
        llm: LlmProtocol | None = None,
        prompt_builder: SchedulingPromptBuilder | None = None,
        sms: SmsSimulationService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or create_knowledge_base_retriever(self.settings)
        self.llm = llm
        self.prompt_builder = prompt_builder or SchedulingPromptBuilder(
            max_context_characters=self.settings.rag_max_context_characters,
        )
        self.sms = sms or SmsSimulationService()

    def analyze(self, transcript: str, today: date | None = None) -> AppointmentDebugResponse:
        """Return diagnostic data without persisting raw patient content."""
        analysis_date = today or date.today()
        logger.info(
            "Debug appointment analysis started transcript_chars=%s today=%s",
            len(transcript),
            analysis_date.isoformat(),
        )
        response = AppointmentDebugResponse(status="completed", transcript=transcript)

        try:
            llm = self._get_llm()
            response.direct_bielik_output = self._run_direct_llm(llm, transcript)
        except ServiceError as exc:
            return _failed_response(response, "direct_llm", exc)

        try:
            scheduler = SchedulerService(today=analysis_date)
            passages = self.retriever.retrieve(transcript, limit=self.settings.retrieval_limit)
            response.retrieved_context = passages
        except ServiceError as exc:
            return _failed_response(response, "retrieval", exc)

        try:
            messages = self.prompt_builder.build_messages(
                transcript=transcript,
                retrieved_passages=passages,
                availability_summary=scheduler.availability_summary(),
                today=scheduler.week_start.isoformat(),
            )
            response.rag_bielik_raw_output = llm.generate(messages)
        except ServiceError as exc:
            return _failed_response(response, "rag_llm", exc)

        try:
            intent = _parse_appointment_intent(response.rag_bielik_raw_output)
            intent = apply_polish_weekday_sanity_checks(intent, transcript, scheduler.week_start)
            response.validated_intent = intent
        except RagAnalysisError as exc:
            return _failed_response(response, "validation", exc)

        try:
            scheduling_result = scheduler.schedule_from_intent(intent)
            response.scheduler_result = SchedulerDebugResult(
                status=scheduling_result.status,
                event=scheduling_result.event,
                explanation=scheduling_result.explanation,
            )
            response.sms_text = self.sms.render(scheduling_result)
        except ServiceError as exc:
            return _failed_response(response, "scheduler", exc)

        logger.info(
            "Debug appointment analysis completed retrieved_passages=%s intent_valid=%s "
            "scheduler_status=%s",
            len(response.retrieved_context),
            response.validated_intent is not None,
            response.scheduler_result.status if response.scheduler_result else None,
        )
        return response

    def _get_llm(self) -> LlmProtocol:
        if self.llm is None:
            from app.services.bielik import BielikLlmService

            self.llm = BielikLlmService(self.settings)
        return self.llm

    @staticmethod
    def _run_direct_llm(llm: LlmProtocol, transcript: str) -> str:
        messages = [
            ConversationMessage(
                role="system",
                content=(
                    "You are a diagnostic assistant. Summarize the Polish patient transcript "
                    "for appointment scheduling. Do not book anything."
                ),
            ),
            ConversationMessage(role="user", content=transcript),
        ]
        return llm.generate(messages)


def _failed_response(
    response: AppointmentDebugResponse,
    stage: str,
    exc: Exception,
) -> AppointmentDebugResponse:
    logger.warning(
        "Debug appointment analysis failed stage=%s error_type=%s",
        stage,
        type(exc).__name__,
    )
    response.status = "failed"
    response.failed_stage = stage  # type: ignore[assignment]
    response.error_message = str(exc)
    return response
