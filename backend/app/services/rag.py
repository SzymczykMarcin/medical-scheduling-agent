import json
import logging
import re
from datetime import date
from typing import Protocol

from pydantic import ValidationError

from app.core.settings import Settings, get_settings
from app.models.appointment import AppointmentIntent
from app.models.rag import ConversationMessage, RetrievedPassage
from app.services.bielik import BielikLlmService
from app.services.exceptions import RagAnalysisError
from app.services.intent_postprocessing import apply_polish_weekday_sanity_checks
from app.services.rag_prompting import SchedulingPromptBuilder
from app.services.rag_retrieval import create_knowledge_base_retriever

logger = logging.getLogger(__name__)


class RetrieverProtocol(Protocol):
    """Interface for transcript-context retrieval."""

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Retrieve relevant RAG passages."""


class LlmProtocol(Protocol):
    """Interface for local LLM generation."""

    def generate(self, messages: list) -> str:
        """Generate a model response."""


class RagAnalysisService:
    """Analyze transcripts with a local Bielik RAG pipeline."""

    def __init__(
        self,
        settings: Settings | None = None,
        retriever: RetrieverProtocol | None = None,
        llm: LlmProtocol | None = None,
        prompt_builder: SchedulingPromptBuilder | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or create_knowledge_base_retriever(self.settings)
        self.llm = llm or BielikLlmService(self.settings)
        self.prompt_builder = prompt_builder or SchedulingPromptBuilder(
            max_context_characters=self.settings.rag_max_context_characters,
        )

    def analyze(
        self,
        transcript: str,
        availability_summary: str,
        today: date,
    ) -> AppointmentIntent:
        """Return structured appointment intent from transcript, RAG context and calendar."""
        return self.analyze_transcript(
            transcript=transcript,
            availability_summary=availability_summary,
            today=today,
        )

    def analyze_transcript(
        self,
        transcript: str,
        availability_summary: str | None = None,
        today: date | None = None,
    ) -> AppointmentIntent:
        """Return structured appointment intent from transcript and RAG context."""
        if self.settings.demo_mode:
            return AppointmentIntent(
                visit_reason="Ból gardła i gorączka",
                procedure_hint="Konsultacja lekarza rodzinnego",
                preferred_time="jutro po południu",
                urgency="standardowa",
                duration_minutes=30,
                confidence=0.75,
                explanation="Reguły demo wskazują standardową konsultację POZ.",
            )

        if not transcript.strip():
            raise RagAnalysisError("Transcript is empty.")

        passages = self.retriever.retrieve(transcript, limit=self.settings.retrieval_limit)
        messages = self.prompt_builder.build_messages(
            transcript=transcript,
            retrieved_passages=passages,
            availability_summary=availability_summary or "No calendar availability was provided.",
            today=(today or date.today()).isoformat(),
        )
        raw_response = self.llm.generate(messages)
        try:
            intent = _parse_appointment_intent(raw_response)
        except RagAnalysisError:
            logger.warning("Initial Bielik appointment JSON was invalid; requesting JSON repair.")
            raw_response = self.llm.generate(
                _build_json_repair_messages(
                    transcript=transcript,
                    invalid_response=raw_response,
                )
            )
            intent = _parse_appointment_intent(raw_response)
        intent = apply_polish_weekday_sanity_checks(intent, transcript, today or date.today())
        logger.info(
            "RAG analysis completed duration_minutes=%s urgency=%s sources=%s",
            intent.duration_minutes,
            intent.urgency,
            len(passages),
        )
        return intent


def _parse_appointment_intent(raw_response: str) -> AppointmentIntent:
    payload = _extract_json_object(raw_response)
    try:
        data = json.loads(payload)
        return AppointmentIntent.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Invalid Bielik appointment JSON: %s", raw_response)
        raise RagAnalysisError("Bielik returned invalid appointment JSON.") from exc


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    object_match = re.search(r"(\{.*\})", stripped, flags=re.DOTALL)
    if object_match:
        return object_match.group(1)

    raise RagAnalysisError("Bielik response did not contain a JSON object.")


def _build_json_repair_messages(
    transcript: str,
    invalid_response: str,
) -> list[ConversationMessage]:
    return [
        ConversationMessage(
            role="system",
            content=(
                "You repair invalid LLM output into one valid JSON object. "
                "Do not use tools, markdown, XML tags, or explanations. "
                "Return only JSON matching the appointment intent schema."
            ),
        ),
        ConversationMessage(
            role="user",
            content=f"""Patient transcript:
{transcript}

Invalid previous output:
{invalid_response[:3000]}

Return exactly one JSON object with keys:
visit_reason, procedure_hint, preferred_time, preferred_days, preferred_time_windows,
excluded_days, specific_datetime, urgency, duration_minutes, confidence,
requires_human_callback, explanation.
Use duration_minutes as one of 30, 60, 90, 120.
""",
        ),
    ]
