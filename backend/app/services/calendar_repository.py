from datetime import datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.engine import make_url
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.models.calendar import CalendarEvent


class CalendarRepository(Protocol):
    """Persistence boundary for appointment calendar events."""

    def list_events(self) -> list[CalendarEvent]:
        """Return all persisted calendar events."""

    def add_event(self, event: CalendarEvent) -> None:
        """Persist one calendar event."""

    def is_empty(self) -> bool:
        """Return true when no calendar events exist."""


class MemoryCalendarRepository:
    """In-process calendar repository for focused tests and debug flows."""

    def __init__(self, initial_events: list[CalendarEvent] | None = None) -> None:
        self._events = list(initial_events or [])

    def list_events(self) -> list[CalendarEvent]:
        return sorted(self._events, key=lambda event: event.start)

    def add_event(self, event: CalendarEvent) -> None:
        self._events.append(event)

    def is_empty(self) -> bool:
        return not self._events


class CalendarEventRecord(SQLModel, table=True):
    """SQL record for persisted demo calendar events."""

    __tablename__ = "calendar_events"

    id: str = Field(primary_key=True)
    patient_label: str
    title: str
    start: datetime
    end: datetime
    duration_minutes: int
    status: str = "scheduled"

    @classmethod
    def from_domain(cls, event: CalendarEvent) -> "CalendarEventRecord":
        return cls(
            id=event.id,
            patient_label=event.patient_label,
            title=event.title,
            start=event.start,
            end=event.end,
            duration_minutes=event.duration_minutes,
            status=event.status,
        )

    def to_domain(self) -> CalendarEvent:
        return CalendarEvent(
            id=self.id,
            patient_label=self.patient_label,
            title=self.title,
            start=self.start,
            end=self.end,
            duration_minutes=self.duration_minutes,
            status=self.status,
        )


class SqlCalendarRepository:
    """SQL-backed calendar repository for local SQLite and managed databases."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        url = make_url(database_url)
        self._ensure_sqlite_parent_exists(url)
        connect_args = {"check_same_thread": False} if url.drivername == "sqlite" else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        SQLModel.metadata.create_all(self._engine)

    def list_events(self) -> list[CalendarEvent]:
        with Session(self._engine) as session:
            records = session.exec(
                select(CalendarEventRecord).order_by(CalendarEventRecord.start)
            ).all()
            return [record.to_domain() for record in records]

    def add_event(self, event: CalendarEvent) -> None:
        with Session(self._engine) as session:
            session.merge(CalendarEventRecord.from_domain(event))
            session.commit()

    def is_empty(self) -> bool:
        with Session(self._engine) as session:
            return session.exec(select(CalendarEventRecord.id).limit(1)).first() is None

    @staticmethod
    def _ensure_sqlite_parent_exists(url) -> None:
        if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
            return
        Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


SqliteCalendarRepository = SqlCalendarRepository
