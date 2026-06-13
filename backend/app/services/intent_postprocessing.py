import re
from datetime import date, datetime, time, timedelta

from app.models.appointment import AppointmentIntent


def apply_polish_weekday_sanity_checks(
    intent: AppointmentIntent,
    transcript: str,
    reference_date: date,
) -> AppointmentIntent:
    """Apply deterministic Polish scheduling rules after LLM intent extraction."""
    normalized = _normalize_polish_text(transcript)
    if _requires_callback_due_to_missing_reason(normalized):
        return intent.model_copy(
            update={
                "requires_human_callback": True,
                "confidence": min(intent.confidence, 0.2),
                "explanation": (
                    f"{intent.explanation} Pacjent nie podał powodu wizyty, "
                    "więc wymagany jest kontakt telefoniczny."
                ),
            }
        )

    week_start = reference_date - timedelta(days=reference_date.weekday())
    explicit_days = _extract_polish_weekday_dates(normalized, week_start)
    explicit_exclusions = _extract_polish_excluded_weekday_dates(normalized, week_start)
    exact_time = _extract_exact_time(normalized)

    if not explicit_days and not explicit_exclusions and exact_time is None:
        return intent

    allowed_dates = [day.isoformat() for day in explicit_days]
    excluded_dates = sorted({*intent.excluded_days, *(day.isoformat() for day in explicit_exclusions)})
    update: dict[str, object] = {"excluded_days": excluded_dates}

    if allowed_dates:
        update["preferred_days"] = allowed_dates

        if exact_time is not None and len(explicit_days) == 1:
            update["specific_datetime"] = datetime.combine(explicit_days[0], exact_time).isoformat()
            update["preferred_time_windows"] = []
        elif _has_only_day_preference(normalized):
            update["preferred_time_windows"] = []
            update["specific_datetime"] = None
        else:
            update["preferred_time_windows"] = [
                window.model_copy(update={"date": None}) for window in intent.preferred_time_windows
            ]
            specific_datetime = intent.specific_datetime
            if specific_datetime and not any(specific_datetime.startswith(day) for day in allowed_dates):
                update["specific_datetime"] = None
                update["explanation"] = (
                    f"{intent.explanation} Termin szczegółowy odrzucono, bo transkrypcja wskazuje: "
                    f"{', '.join(allowed_dates)}."
                )

    return intent.model_copy(update=update)


def _requires_callback_due_to_missing_reason(normalized_transcript: str) -> bool:
    vague_patterns = (
        r"\bnie wiem jeszcze po co\b",
        r"\bnie wiem po co\b",
        r"\bnie wiem jaka wizyta\b",
        r"\bnie wiem do kogo\b",
        r"\bbez konkretnego powodu\b",
    )
    return any(re.search(pattern, normalized_transcript) for pattern in vague_patterns)


def _has_only_day_preference(normalized_transcript: str) -> bool:
    if _contains_time_constraint(normalized_transcript):
        return False

    day_only_patterns = (
        r"\bdowolna wolna godzina\b",
        r"\bdowolna godzina\b",
        r"\bjakakolwiek godzina\b",
        r"\bo dowolnej godzinie\b",
        r"\bnajlepiej w\b",
        r"\bnajlepiej we\b",
        r"\bmoze byc w\b",
        r"\bmoze byc we\b",
    )
    return any(re.search(pattern, normalized_transcript) for pattern in day_only_patterns)


def _contains_time_constraint(normalized_transcript: str) -> bool:
    time_patterns = (
        r"\bpo\s+(?:godzinie\s+)?(?:\d{1,2}|[a-z]+)",
        r"\bprzed\s+(?:godzina\s+)?(?:\d{1,2}|[a-z]+)",
        r"\bdo\s+(?:godziny\s+)?(?:\d{1,2}|[a-z]+)",
        r"\bod\s+(?:godziny\s+)?(?:\d{1,2}|[a-z]+)",
        r"\bnie pozniej niz\s+(?:\d{1,2}|[a-z]+)",
        r"\b\d{1,2}[:.]\d{2}\b",
    )
    return any(re.search(pattern, normalized_transcript) for pattern in time_patterns)


def _extract_exact_time(normalized_transcript: str) -> time | None:
    if not _contains_exact_time_marker(normalized_transcript):
        return None

    numeric_match = re.search(
        r"\b(?:konkretnie|dokladnie)?\s*(?:o|na)\s+(?:godzine\s+|godzina\s+)?"
        r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\b",
        normalized_transcript,
    )
    if numeric_match:
        return _safe_time(
            hour=int(numeric_match.group("hour")),
            minute=int(numeric_match.group("minute") or "0"),
        )

    word_match = re.search(
        r"\b(?:konkretnie|dokladnie)?\s*(?:o|na)\s+(?:godzine\s+|godzina\s+)?"
        r"(?P<hour_word>[a-z]+)(?:\s+rano|\s+po poludniu)?\b",
        normalized_transcript,
    )
    if not word_match:
        return None

    hour = POLISH_HOUR_WORDS.get(word_match.group("hour_word"))
    if hour is None:
        return None
    return _safe_time(hour=hour, minute=0)


def _contains_exact_time_marker(normalized_transcript: str) -> bool:
    if re.search(r"\b(?:konkretnie|dokladnie)\b", normalized_transcript):
        return True
    return bool(re.search(r"\b(?:o|na)\s+(?:godzine\s+|godzina\s+)?", normalized_transcript))


def _safe_time(hour: int, minute: int) -> time | None:
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _extract_polish_weekday_dates(normalized_transcript: str, week_start: date) -> list[date]:
    excluded = set(_extract_polish_excluded_weekday_dates(normalized_transcript, week_start))
    result: list[date] = []

    for weekday, offset in POLISH_WEEKDAY_OFFSETS.items():
        if re.search(rf"\b{weekday}\b", normalized_transcript):
            candidate = week_start + timedelta(days=offset)
            if candidate not in excluded and candidate not in result:
                result.append(candidate)

    return result


def _extract_polish_excluded_weekday_dates(normalized_transcript: str, week_start: date) -> list[date]:
    result: list[date] = []

    for weekday, offset in POLISH_WEEKDAY_OFFSETS.items():
        if re.search(rf"\b(?:nie|bez|oprocz)\s+{weekday}\b", normalized_transcript):
            candidate = week_start + timedelta(days=offset)
            if candidate not in result:
                result.append(candidate)

    return result


def _normalize_polish_text(value: str) -> str:
    replacements = str.maketrans(
        {
            "ą": "a",
            "ć": "c",
            "ę": "e",
            "ł": "l",
            "ń": "n",
            "ó": "o",
            "ś": "s",
            "ź": "z",
            "ż": "z",
        }
    )
    return value.lower().translate(replacements)


POLISH_WEEKDAY_OFFSETS = {
    "poniedzialek": 0,
    "poniedzialku": 0,
    "wtorek": 1,
    "wtorku": 1,
    "sroda": 2,
    "srode": 2,
    "srody": 2,
    "czwartek": 3,
    "czwartku": 3,
    "piatek": 4,
    "piatku": 4,
}

POLISH_HOUR_WORDS = {
    "pierwszej": 1,
    "drugiej": 2,
    "trzeciej": 3,
    "czwartej": 4,
    "piatej": 5,
    "szostej": 6,
    "siodmej": 7,
    "osmej": 8,
    "dziewiatej": 9,
    "dziesiatej": 10,
    "jedenastej": 11,
    "dwunastej": 12,
    "trzynastej": 13,
    "czternastej": 14,
    "pietnastej": 15,
    "szesnastej": 16,
    "siedemnastej": 17,
    "osiemnastej": 18,
}
