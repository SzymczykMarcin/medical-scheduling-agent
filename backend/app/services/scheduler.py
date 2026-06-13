from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from app.models.appointment import AppointmentIntent, AppointmentStatus, PreferredTimeWindow
from app.models.calendar import CalendarEvent

CLINIC_OPEN_HOUR = 9
CLINIC_CLOSE_HOUR = 17
ALLOWED_DURATIONS = (30, 60, 90, 120)


@dataclass(frozen=True)
class FreeWindow:
    """One free calendar window."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class SchedulingResult:
    """Result of deterministic appointment scheduling."""

    status: AppointmentStatus
    event: CalendarEvent | None
    explanation: str


class SchedulerService:
    """Serve and update the in-memory demo appointment calendar."""

    def __init__(self, today: date | None = None) -> None:
        self._week_start = _week_start(today or date.today())
        self._events: list[CalendarEvent] = build_seed_appointments(self._week_start)

    def list_events(self) -> list[CalendarEvent]:
        """Return appointments sorted by start date."""
        return sorted(self._events, key=lambda event: event.start)

    @property
    def week_start(self) -> date:
        """Return Monday of the active demo calendar week."""
        return self._week_start

    def callback_result(self, explanation: str) -> SchedulingResult:
        """Return a deterministic callback result without mutating the calendar."""
        return SchedulingResult(status="needs_callback", event=None, explanation=explanation)

    def book_from_intent(self, intent: AppointmentIntent) -> CalendarEvent:
        """Book the next suitable slot for an appointment intent."""
        result = self.schedule_from_intent(intent)
        if result.event is None:
            raise RuntimeError(result.explanation)
        return result.event

    def schedule_from_intent(self, intent: AppointmentIntent) -> SchedulingResult:
        """Try to book an appointment using extracted patient preferences."""
        duration_minutes = _normalize_duration(intent.duration_minutes)
        if intent.requires_human_callback or intent.confidence < 0.35:
            return SchedulingResult(
                status="needs_callback",
                event=None,
                explanation="Zgłoszenie nie było wystarczająco jasne do automatycznego umówienia.",
            )

        start = self._select_slot(intent, duration_minutes)
        if start is None:
            return SchedulingResult(
                status="needs_callback",
                event=None,
                explanation="Nie znaleziono pasującego wolnego terminu w kalendarzu.",
            )

        event = CalendarEvent(
            id=str(uuid4()),
            patient_label="Pacjent demo",
            title=intent.visit_reason,
            start=start,
            end=start + timedelta(minutes=duration_minutes),
            duration_minutes=duration_minutes,
        )
        self._events.append(event)
        return SchedulingResult(
            status="scheduled",
            event=event,
            explanation="Wizyta została umówiona w pierwszym pasującym wolnym terminie.",
        )

    def availability_summary(self) -> str:
        """Render free windows as compact text for the LLM prompt."""
        windows = self.list_free_windows()
        if not windows:
            return "No free windows in the current clinic week."

        return "\n".join(
            f"- {window.start.strftime('%Y-%m-%d %H:%M')} - {window.end.strftime('%H:%M')}"
            for window in windows
        )

    def list_free_windows(self) -> list[FreeWindow]:
        """Return free windows between seeded appointments for the clinic week."""
        windows: list[FreeWindow] = []
        for day_offset in range(5):
            day = self._week_start + timedelta(days=day_offset)
            day_start = datetime.combine(day, time(hour=CLINIC_OPEN_HOUR))
            day_end = datetime.combine(day, time(hour=CLINIC_CLOSE_HOUR))
            day_events = [
                event for event in self.list_events() if event.start.date() == day
            ]
            cursor = day_start
            for event in day_events:
                if event.start > cursor:
                    windows.append(FreeWindow(start=cursor, end=event.start))
                cursor = max(cursor, event.end)
            if cursor < day_end:
                windows.append(FreeWindow(start=cursor, end=day_end))
        return windows

    def _find_next_slot(self, duration_minutes: int) -> datetime:
        cursor = datetime.combine(self._week_start, time(hour=CLINIC_OPEN_HOUR))

        while True:
            candidate_end = cursor + timedelta(minutes=duration_minutes)
            office_end = cursor.replace(hour=CLINIC_CLOSE_HOUR, minute=0)
            if candidate_end <= office_end and not self._overlaps(cursor, candidate_end):
                return cursor

            cursor += timedelta(minutes=15)
            if cursor >= office_end:
                next_day = cursor.date() + timedelta(days=1)
                cursor = datetime.combine(next_day, time(hour=CLINIC_OPEN_HOUR))

    def _overlaps(self, start: datetime, end: datetime) -> bool:
        return any(start < event.end and end > event.start for event in self._events)

    def _select_slot(self, intent: AppointmentIntent, duration_minutes: int) -> datetime | None:
        specific_slot = _parse_iso_datetime(intent.specific_datetime)
        if specific_slot:
            if self._slot_is_available(specific_slot, duration_minutes):
                return specific_slot
            return None

        candidate_dates = _candidate_dates(intent, self._week_start)
        for candidate_date in candidate_dates:
            for window in _candidate_windows(intent, candidate_date):
                slot = self._find_first_slot_in_window(window, duration_minutes)
                if slot is not None:
                    return slot

        if intent.preferred_days or intent.preferred_time_windows or intent.excluded_days:
            return None

        for window in self.list_free_windows():
            slot = self._find_first_slot_in_window(window, duration_minutes)
            if slot is not None:
                return slot
        return None

    def _find_first_slot_in_window(self, window: FreeWindow, duration_minutes: int) -> datetime | None:
        cursor = _ceil_to_quarter_hour(window.start)
        while cursor + timedelta(minutes=duration_minutes) <= window.end:
            if self._slot_is_available(cursor, duration_minutes):
                return cursor
            cursor += timedelta(minutes=15)
        return None

    def _slot_is_available(self, start: datetime, duration_minutes: int) -> bool:
        end = start + timedelta(minutes=duration_minutes)
        if start.date() < self._week_start or start.date() > self._week_start + timedelta(days=4):
            return False
        office_start = datetime.combine(start.date(), time(hour=CLINIC_OPEN_HOUR))
        office_end = datetime.combine(start.date(), time(hour=CLINIC_CLOSE_HOUR))
        return start >= office_start and end <= office_end and not self._overlaps(start, end)


def build_seed_appointments(week_start: date) -> list[CalendarEvent]:
    """Create deterministic demo appointments with easy scheduling gaps."""
    definitions = [
        (0, "09:00", 30, "Pacjent A", "Przedłużenie recepty"),
        (0, "10:30", 30, "Pacjent B", "Kontrola ciśnienia"),
        (0, "13:00", 60, "Pacjent C", "Wizyta kontrolna"),
        (0, "16:00", 30, "Pacjent D", "Omówienie wyników badań"),
        (1, "09:30", 60, "Pacjent E", "Pierwsza konsultacja"),
        (1, "12:00", 30, "Pacjent F", "Kwalifikacja do szczepienia"),
        (1, "14:30", 30, "Pacjent G", "Przegląd leków"),
        (2, "09:00", 30, "Pacjent H", "Rutynowa wizyta POZ"),
        (2, "11:00", 90, "Pacjent I", "Rozszerzona konsultacja"),
        (2, "15:00", 30, "Pacjent J", "Telefon kontrolny"),
        (3, "10:00", 30, "Pacjent K", "Objawy infekcji"),
        (3, "11:30", 60, "Pacjent L", "Kontrola choroby przewlekłej"),
        (3, "15:30", 30, "Pacjent M", "Skierowanie"),
        (4, "09:00", 60, "Pacjent N", "Nowy pacjent"),
        (4, "11:30", 30, "Pacjent O", "Omówienie wyników"),
        (4, "14:00", 60, "Pacjent P", "Wizyta kontrolna"),
    ]

    return [
        _build_event(
            week_start=week_start,
            day_offset=day_offset,
            start_text=start_text,
            duration_minutes=duration_minutes,
            patient_label=patient_label,
            title=title,
            event_id=f"seed-{index}",
        )
        for index, (day_offset, start_text, duration_minutes, patient_label, title) in enumerate(
            definitions,
            start=1,
        )
    ]


def _build_event(
    week_start: date,
    day_offset: int,
    start_text: str,
    duration_minutes: int,
    patient_label: str,
    title: str,
    event_id: str,
) -> CalendarEvent:
    hour, minute = (int(part) for part in start_text.split(":"))
    start = datetime.combine(week_start + timedelta(days=day_offset), time(hour=hour, minute=minute))
    return CalendarEvent(
        id=event_id,
        patient_label=patient_label,
        title=title,
        start=start,
        end=start + timedelta(minutes=duration_minutes),
        duration_minutes=duration_minutes,
    )


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _normalize_duration(duration_minutes: int) -> int:
    return min(ALLOWED_DURATIONS, key=lambda value: abs(value - duration_minutes))


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_time(value: str | None, default: time) -> time:
    if not value:
        return default
    try:
        hour, minute = (int(part) for part in value.split(":", maxsplit=1))
        return time(hour=hour, minute=minute)
    except ValueError:
        return default


def _candidate_dates(intent: AppointmentIntent, week_start: date) -> list[date]:
    excluded = {
        parsed for value in intent.excluded_days if (parsed := _parse_iso_date(value)) is not None
    }
    preferred = [
        parsed for value in intent.preferred_days if (parsed := _parse_iso_date(value)) is not None
    ]
    dates = preferred or [week_start + timedelta(days=offset) for offset in range(5)]
    return [day for day in dates if day.weekday() < 5 and day not in excluded]


def _candidate_windows(intent: AppointmentIntent, candidate_date: date) -> list[FreeWindow]:
    matching_windows = [
        window
        for window in intent.preferred_time_windows
        if window.date in {None, candidate_date.isoformat()}
    ]
    if not matching_windows:
        return [
            FreeWindow(
                start=datetime.combine(candidate_date, time(hour=CLINIC_OPEN_HOUR)),
                end=datetime.combine(candidate_date, time(hour=CLINIC_CLOSE_HOUR)),
            )
        ]
    return [_window_to_free_window(window, candidate_date) for window in matching_windows]


def _window_to_free_window(window: PreferredTimeWindow, candidate_date: date) -> FreeWindow:
    start_time = _parse_time(window.start_time, time(hour=CLINIC_OPEN_HOUR))
    end_time = _parse_time(window.end_time, time(hour=CLINIC_CLOSE_HOUR))
    return FreeWindow(
        start=datetime.combine(candidate_date, start_time),
        end=datetime.combine(candidate_date, end_time),
    )


def _ceil_to_quarter_hour(value: datetime) -> datetime:
    remainder = value.minute % 15
    if remainder == 0 and value.second == 0 and value.microsecond == 0:
        return value
    rounded = value + timedelta(minutes=15 - remainder)
    return rounded.replace(second=0, microsecond=0)
