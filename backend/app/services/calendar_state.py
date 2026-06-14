from app.core.settings import get_settings
from app.services.calendar_repository import MemoryCalendarRepository, SqlCalendarRepository
from app.services.scheduler import SchedulerService


def create_calendar_scheduler() -> SchedulerService:
    """Create the configured shared calendar scheduler."""
    settings = get_settings()
    if settings.calendar_storage_backend == "memory":
        repository = MemoryCalendarRepository()
    else:
        repository = SqlCalendarRepository(settings.effective_database_url)
    return SchedulerService(repository=repository, seed_if_empty=settings.seed_demo_calendar)


calendar_scheduler = create_calendar_scheduler()
