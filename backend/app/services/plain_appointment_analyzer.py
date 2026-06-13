import json
import logging
import re
from datetime import date
from typing import Protocol

from pydantic import ValidationError

from app.core.settings import Settings, get_settings
from app.models.appointment import AppointmentIntent
from app.models.rag import ConversationMessage
from app.services.bielik import BielikLlmService
from app.services.exceptions import RagAnalysisError
from app.services.intent_postprocessing import apply_polish_weekday_sanity_checks

logger = logging.getLogger(__name__)


class LlmProtocol(Protocol):
    """Interface for local LLM generation."""

    def generate(self, messages: list[ConversationMessage]) -> str:
        """Generate a model response."""


class PlainAppointmentAnalyzer:
    """Extract scheduling intent from transcript with Bielik and no RAG."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LlmProtocol | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or BielikLlmService(self.settings)

    def analyze(
        self,
        transcript: str,
        availability_summary: str,
        today: date,
    ) -> AppointmentIntent:
        """Return appointment intent extracted from a Polish transcript."""
        if self.settings.demo_mode:
            return AppointmentIntent(
                visit_reason="Ból gardła i gorączka",
                procedure_hint="Konsultacja lekarza rodzinnego",
                preferred_time="jutro po południu",
                preferred_days=[],
                urgency="standardowa",
                duration_minutes=30,
                confidence=0.75,
                requires_human_callback=False,
                explanation="Intencja wizyty w trybie demonstracyjnym.",
            )

        if not transcript.strip():
            raise RagAnalysisError("Transcript is empty.")

        raw_response = self.llm.generate(
            _build_messages(
                transcript=transcript,
                availability_summary=availability_summary,
                today=today,
            )
        )
        intent = _parse_intent(raw_response)
        intent = apply_polish_weekday_sanity_checks(intent, transcript, today)
        logger.info(
            "Plain appointment analysis completed duration=%s confidence=%s callback=%s",
            intent.duration_minutes,
            intent.confidence,
            intent.requires_human_callback,
        )
        return intent


def _build_messages(
    transcript: str,
    availability_summary: str,
    today: date,
) -> list[ConversationMessage]:
    system_prompt = """You are a Polish medical appointment scheduling assistant.
Extract structured scheduling data from the transcript.
Do not diagnose the patient.
Estimate visit duration only for calendar scheduling.
Use only these duration values: 30, 60, 90, 120.
Keep patient-facing text in Polish.
When the patient mentions a weekday in Polish, convert it to the matching date in the current clinic week.
If the request is unclear, contradictory, unsafe, or cannot be scheduled automatically, set requires_human_callback=true.
Return only valid JSON. Do not add markdown.
"""
    user_prompt = f"""Today is {today.isoformat()}.

Available clinic windows:
{availability_summary}

Patient transcript:
{transcript}

Return JSON with exactly these keys:
{{
  "visit_reason": "krotki polski opis powodu wizyty",
  "procedure_hint": "krotka polska kategoria/procedura albo null",
  "preferred_time": "krotki polski opis preferencji terminu albo null",
  "preferred_days": ["YYYY-MM-DD"],
  "preferred_time_windows": [
    {{"date": "YYYY-MM-DD or null", "start_time": "HH:MM or null", "end_time": "HH:MM or null"}}
  ],
  "excluded_days": ["YYYY-MM-DD"],
  "specific_datetime": "YYYY-MM-DDTHH:MM:SS or null",
  "urgency": "pilnosc umawiania, nie diagnoza",
  "duration_minutes": 30,
  "confidence": 0.0,
  "requires_human_callback": false,
  "explanation": "krotkie polskie wyjasnienie"
}}
"""
    return [
        ConversationMessage(role="system", content=system_prompt),
        ConversationMessage(role="user", content=user_prompt),
    ]


def _parse_intent(raw_response: str) -> AppointmentIntent:
    payload = _extract_json_object(raw_response)
    try:
        data = json.loads(payload)
        return AppointmentIntent.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Invalid Bielik plain appointment JSON: %s", raw_response)
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
