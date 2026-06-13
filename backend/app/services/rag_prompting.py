from pathlib import Path

from app.models.rag import ConversationMessage, RetrievedPassage

SCHEDULING_DEVELOPER_PROMPT = """You are a Polish medical appointment scheduling assistant.
Use retrieved scheduling rules as the source of truth.
Do not diagnose the patient.
Estimate appointment duration only for scheduling purposes.
Use only these duration values: 30, 60, 90, 120.
Keep patient-facing text in Polish.
Use the calendar availability only to extract scheduling preferences; the deterministic scheduler will book the final slot.
Return only valid JSON matching the requested schema.
"""


class SchedulingPromptBuilder:
    """Build Bielik prompts for appointment scheduling analysis."""

    def __init__(self, max_context_characters: int) -> None:
        self._max_context_characters = max_context_characters

    def build_messages(
        self,
        transcript: str,
        retrieved_passages: list[RetrievedPassage],
        availability_summary: str,
        today: str,
    ) -> list[ConversationMessage]:
        """Create a compact RAG prompt for structured appointment extraction."""
        context = self._build_context_block(retrieved_passages)
        user_prompt = f"""Today is {today}.

Retrieved scheduling rules:
{context}

Available clinic windows:
{availability_summary}

Patient transcript:
{transcript}

Return JSON with exactly these keys:
{{
  "visit_reason": "krótki polski opis powodu wizyty",
  "procedure_hint": "krótka polska kategoria/procedura albo null",
  "preferred_time": "krótki polski opis preferencji terminu albo null",
  "preferred_days": ["YYYY-MM-DD"],
  "preferred_time_windows": [
    {{"date": "YYYY-MM-DD or null", "start_time": "HH:MM or null", "end_time": "HH:MM or null"}}
  ],
  "excluded_days": ["YYYY-MM-DD"],
  "specific_datetime": "YYYY-MM-DDTHH:MM:SS or null",
  "urgency": "pilność umawiania, nie diagnoza",
  "duration_minutes": 30,
  "confidence": 0.0,
  "requires_human_callback": false,
  "explanation": "krótkie polskie wyjaśnienie oparte na regułach RAG"
}}
"""
        return [
            ConversationMessage(role="system", content=SCHEDULING_DEVELOPER_PROMPT),
            ConversationMessage(role="user", content=user_prompt),
        ]

    def _build_context_block(self, retrieved_passages: list[RetrievedPassage]) -> str:
        if not retrieved_passages:
            return "No retrieved scheduling context."

        rendered_parts: list[str] = []
        used_characters = 0
        for index, passage in enumerate(retrieved_passages, start=1):
            source_label = _safe_source_label(passage)
            heading = f" section={passage.heading}" if passage.heading else ""
            fragment = f"[{index}] source={source_label}{heading}\n{passage.content.strip()}\n"
            if used_characters + len(fragment) > self._max_context_characters:
                break
            rendered_parts.append(fragment)
            used_characters += len(fragment)

        return "\n".join(rendered_parts) if rendered_parts else "No context within limit."


def _safe_source_label(passage: RetrievedPassage) -> str:
    if passage.heading:
        return passage.heading

    filename = str(passage.source_path or "").replace("\\", "/").split("/")[-1]
    stem = Path(filename).stem if filename else "scheduling-rules"
    return stem.replace("_", "-")[:80] or "scheduling-rules"
