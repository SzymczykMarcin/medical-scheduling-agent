from datetime import date

import pytest

from app.core.settings import Settings
from app.models.rag import ConversationMessage
from app.services.exceptions import RagAnalysisError
from app.services.plain_appointment_analyzer import PlainAppointmentAnalyzer


class FakeLlm:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[ConversationMessage] = []

    def generate(self, messages: list[ConversationMessage]) -> str:
        self.messages = messages
        return self.response


def test_plain_analyzer_parses_valid_bielik_json() -> None:
    llm = FakeLlm(
        """
        {
          "visit_reason": "Sore throat",
          "procedure_hint": "GP consultation",
          "preferred_time": "Tuesday after 10",
          "preferred_days": ["2026-06-09"],
          "preferred_time_windows": [
            {"date": "2026-06-09", "start_time": "10:00", "end_time": null}
          ],
          "excluded_days": [],
          "specific_datetime": null,
          "urgency": "standard",
          "duration_minutes": 30,
          "confidence": 0.82,
          "requires_human_callback": false,
          "explanation": "The patient asked for Tuesday after 10."
        }
        """
    )
    analyzer = PlainAppointmentAnalyzer(settings=Settings(demo_mode=False), llm=llm)

    intent = analyzer.analyze(
        transcript="We wtorek po 10 prosze o wizyte.",
        availability_summary="- 2026-06-09 10:30 - 12:00",
        today=date(2026, 6, 12),
    )

    assert intent.duration_minutes == 30
    assert intent.preferred_days == ["2026-06-09"]
    assert llm.messages
    assert "2026-06-09 10:30 - 12:00" in llm.messages[-1].content


def test_plain_analyzer_rejects_invalid_json() -> None:
    analyzer = PlainAppointmentAnalyzer(settings=Settings(demo_mode=False), llm=FakeLlm("not json"))

    with pytest.raises(RagAnalysisError, match="JSON"):
        analyzer.analyze(
            transcript="Potrzebuje wizyty.",
            availability_summary="- 2026-06-09 10:30 - 12:00",
            today=date(2026, 6, 12),
        )


def test_plain_analyzer_overrides_wrong_llm_weekday_from_polish_transcript() -> None:
    llm = FakeLlm(
        """
        {
          "visit_reason": "Kontrola gardla",
          "procedure_hint": "Konsultacja lekarza rodzinnego",
          "preferred_time": "wtorek po 10",
          "preferred_days": ["2026-06-11"],
          "preferred_time_windows": [
            {"date": "2026-06-11", "start_time": "10:00", "end_time": null}
          ],
          "excluded_days": [],
          "specific_datetime": "2026-06-11T10:00:00",
          "urgency": "standard",
          "duration_minutes": 30,
          "confidence": 0.82,
          "requires_human_callback": false,
          "explanation": "Model omylkowo wybral czwartek."
        }
        """
    )
    analyzer = PlainAppointmentAnalyzer(settings=Settings(demo_mode=False), llm=llm)

    intent = analyzer.analyze(
        transcript="Poprosze wizyte we wtorek po 10.",
        availability_summary="- 2026-06-09 10:30 - 12:00",
        today=date(2026, 6, 8),
    )

    assert intent.preferred_days == ["2026-06-09"]
    assert intent.preferred_time_windows[0].date is None
    assert intent.specific_datetime is None
