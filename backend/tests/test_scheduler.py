from datetime import date

from app.models.appointment import AppointmentIntent, PreferredTimeWindow
from app.services.scheduler import SchedulerService, build_seed_appointments


def test_seed_appointments_create_easy_gaps() -> None:
    events = build_seed_appointments(date(2026, 6, 8))

    assert len(events) == 16
    assert events[0].start.isoformat() == "2026-06-08T09:00:00"
    assert events[1].start.isoformat() == "2026-06-08T10:30:00"
    assert events[2].start.isoformat() == "2026-06-08T13:00:00"


def test_scheduler_books_first_available_half_hour_gap() -> None:
    scheduler = SchedulerService(today=date(2026, 6, 12))
    intent = AppointmentIntent(
        visit_reason="Short consultation",
        urgency="standard",
        duration_minutes=30,
        confidence=0.9,
        explanation="Demo.",
    )

    event = scheduler.book_from_intent(intent)

    assert event.start.isoformat() == "2026-06-08T09:30:00"
    assert event.end.isoformat() == "2026-06-08T10:00:00"


def test_scheduler_books_first_available_two_hour_gap() -> None:
    scheduler = SchedulerService(today=date(2026, 6, 12))
    intent = AppointmentIntent(
        visit_reason="Extended consultation",
        urgency="standard",
        duration_minutes=120,
        confidence=0.9,
        explanation="Demo.",
    )

    event = scheduler.book_from_intent(intent)

    assert event.start.isoformat() == "2026-06-08T11:00:00"
    assert event.end.isoformat() == "2026-06-08T13:00:00"


def test_scheduler_rejects_occupied_specific_datetime() -> None:
    scheduler = SchedulerService(today=date(2026, 6, 12))
    intent = AppointmentIntent(
        visit_reason="Specific busy request",
        urgency="standard",
        duration_minutes=30,
        specific_datetime="2026-06-08T09:00:00",
        confidence=0.9,
        explanation="Demo.",
    )

    result = scheduler.schedule_from_intent(intent)

    assert result.status == "needs_callback"
    assert result.event is None


def test_scheduler_honors_tuesday_after_ten_preference() -> None:
    scheduler = SchedulerService(today=date(2026, 6, 12))
    intent = AppointmentIntent(
        visit_reason="Tuesday preference",
        urgency="standard",
        duration_minutes=60,
        preferred_days=["2026-06-09"],
        preferred_time_windows=[PreferredTimeWindow(start_time="10:00", end_time=None)],
        confidence=0.9,
        explanation="Demo.",
    )

    result = scheduler.schedule_from_intent(intent)

    assert result.status == "scheduled"
    assert result.event is not None
    assert result.event.start.isoformat() == "2026-06-09T10:30:00"


def test_scheduler_honors_multiple_days_and_exclusions() -> None:
    scheduler = SchedulerService(today=date(2026, 6, 12))
    intent = AppointmentIntent(
        visit_reason="Multiple days",
        urgency="standard",
        duration_minutes=90,
        preferred_days=["2026-06-09", "2026-06-11"],
        excluded_days=["2026-06-09"],
        preferred_time_windows=[PreferredTimeWindow(end_time="15:00")],
        confidence=0.9,
        explanation="Demo.",
    )

    result = scheduler.schedule_from_intent(intent)

    assert result.status == "scheduled"
    assert result.event is not None
    assert result.event.start.isoformat() == "2026-06-11T12:30:00"
