from datetime import date

from app.models.appointment import AppointmentIntent
from app.services.calendar_repository import SqliteCalendarRepository
from app.services.scheduler import SchedulerService


def test_sqlite_calendar_repository_persists_scheduled_event(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'calendar.sqlite3'}"
    repository = SqliteCalendarRepository(database_url)
    scheduler = SchedulerService(today=date(2026, 6, 12), repository=repository)
    intent = AppointmentIntent(
        visit_reason="Persistent consultation",
        urgency="standard",
        duration_minutes=30,
        confidence=0.9,
        explanation="Demo.",
    )

    event = scheduler.book_from_intent(intent)
    reloaded_scheduler = SchedulerService(
        today=date(2026, 6, 12),
        repository=SqliteCalendarRepository(database_url),
    )

    event_ids = {stored_event.id for stored_event in reloaded_scheduler.list_events()}
    assert event.id in event_ids
    assert len(reloaded_scheduler.list_events()) == 17


def test_sqlite_calendar_repository_seeds_only_when_empty(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'calendar.sqlite3'}"

    SchedulerService(today=date(2026, 6, 12), repository=SqliteCalendarRepository(database_url))
    reloaded_scheduler = SchedulerService(
        today=date(2026, 6, 12),
        repository=SqliteCalendarRepository(database_url),
    )

    assert len(reloaded_scheduler.list_events()) == 16
