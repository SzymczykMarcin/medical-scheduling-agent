from datetime import date

from app.models.appointment import AppointmentIntent, PreferredTimeWindow
from app.services.intent_postprocessing import apply_polish_weekday_sanity_checks


def _base_intent() -> AppointmentIntent:
    return AppointmentIntent(
        visit_reason="Konsultacja",
        procedure_hint="Konsultacja POZ",
        preferred_time=None,
        preferred_days=[],
        preferred_time_windows=[],
        excluded_days=[],
        specific_datetime=None,
        urgency="standardowa",
        duration_minutes=30,
        confidence=0.9,
        requires_human_callback=False,
        explanation="Test.",
    )


def test_postprocessing_sets_specific_datetime_for_exact_polish_time() -> None:
    intent = _base_intent().model_copy(
        update={
            "preferred_days": ["2026-06-08"],
            "preferred_time_windows": [PreferredTimeWindow(start_time="09:30", end_time="10:30")],
        }
    )

    result = apply_polish_weekday_sanity_checks(
        intent=intent,
        transcript="Pasuje mi konkretnie poniedziałek o dziewiątej rano.",
        reference_date=date(2026, 6, 12),
    )

    assert result.specific_datetime == "2026-06-08T09:00:00"
    assert result.preferred_time_windows == []


def test_postprocessing_keeps_after_time_as_window_not_exact_datetime() -> None:
    intent = _base_intent().model_copy(
        update={
            "preferred_days": ["2026-06-09"],
            "preferred_time_windows": [PreferredTimeWindow(start_time="10:00", end_time=None)],
        }
    )

    result = apply_polish_weekday_sanity_checks(
        intent=intent,
        transcript="Poproszę wizytę we wtorek po godzinie dziesiątej.",
        reference_date=date(2026, 6, 12),
    )

    assert result.specific_datetime is None
    assert result.preferred_time_windows[0].start_time == "10:00"


def test_postprocessing_clears_invented_windows_when_patient_gives_day_only() -> None:
    intent = _base_intent().model_copy(
        update={
            "duration_minutes": 120,
            "preferred_days": ["2026-06-09"],
            "preferred_time_windows": [PreferredTimeWindow(start_time="09:30", end_time="10:30")],
        }
    )

    result = apply_polish_weekday_sanity_checks(
        intent=intent,
        transcript="Chcę umówić krzywą cukrową OGTT. Może być we wtorek, dowolna wolna godzina.",
        reference_date=date(2026, 6, 12),
    )

    assert result.preferred_days == ["2026-06-09"]
    assert result.preferred_time_windows == []


def test_postprocessing_requires_callback_when_visit_reason_is_missing() -> None:
    intent = _base_intent().model_copy(
        update={
            "visit_reason": "nieokreślony",
            "confidence": 0.8,
            "requires_human_callback": False,
        }
    )

    result = apply_polish_weekday_sanity_checks(
        intent=intent,
        transcript="Chcę się umówić na wizytę, ale nie wiem jeszcze po co. Może wtorek.",
        reference_date=date(2026, 6, 12),
    )

    assert result.requires_human_callback is True
    assert result.confidence == 0.2
