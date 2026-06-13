from app.models.calendar import CalendarEvent
from app.services.scheduler import SchedulingResult


class SmsSimulationService:
    """Render deterministic Polish SMS messages for scheduling results."""

    def render(self, scheduling_result: SchedulingResult) -> str:
        """Render deterministic SMS text for a scheduling result."""
        if scheduling_result.event is None:
            return (
                "Nie udało się automatycznie umówić wizyty. "
                "Pracownik placówki skontaktuje się telefonicznie w celu ustalenia terminu."
            )
        return self.render_confirmation(scheduling_result.event)

    def render_confirmation(self, event: CalendarEvent) -> str:
        """Render a successful appointment confirmation."""
        start = event.start.strftime("%d.%m.%Y %H:%M")
        return (
            f"Wizyta została umówiona na {start}. "
            f"Czas trwania: {event.duration_minutes} min. "
            "To jest wiadomość testowa."
        )
