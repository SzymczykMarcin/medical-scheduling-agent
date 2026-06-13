import { CalendarClock, CalendarDays, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchCalendarEvents } from "../api/client";
import type { CalendarEvent } from "../types/api";

const weekdays = ["Pon", "Wt", "Śr", "Czw", "Pt"];
const hours = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"];
const dayStartHour = 9;
const dayEndHour = 17;
const calendarHeight = 640;

type CalendarState = {
  events: CalendarEvent[];
  loading: boolean;
  error: string | null;
};

export function CalendarPage() {
  const [state, setState] = useState<CalendarState>({
    events: [],
    loading: true,
    error: null,
  });

  async function loadCalendarEvents(signal?: AbortSignal) {
    setState((current) => ({ ...current, loading: true, error: null }));

    try {
      const events = await fetchCalendarEvents(signal);
      setState({ events, loading: false, error: null });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      setState({
        events: [],
        loading: false,
        error: error instanceof Error ? error.message : "Nie udało się pobrać wizyt z kalendarza.",
      });
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void loadCalendarEvents(controller.signal);
    return () => controller.abort();
  }, []);

  const visibleEvents = useMemo(
    () => state.events.map(toCalendarPlacement).filter((event) => event !== null),
    [state.events],
  );

  return (
    <section className="page page-grid">
      <div className="page-intro">
        <span className="eyebrow">Grafik placówki</span>
        <h1>Kalendarz wizyt</h1>
        <p>
          Wizyty demonstracyjne są pobierane z backendu. Wolne przestrzenie są celowe, aby agent
          mógł dopasować wizyty trwające 30, 60, 90 albo 120 minut.
        </p>
      </div>

      <div className="calendar-toolbar">
        <div>
          <h2>Widok tygodnia</h2>
          <p>
            {state.loading
              ? "Ładowanie wizyt..."
              : `${state.events.length} ${getPolishVisitCountLabel(state.events.length)} z API`}
          </p>
        </div>
        <button className="button" type="button" onClick={() => loadCalendarEvents()}>
          <RefreshCw size={18} aria-hidden="true" /> Odśwież kalendarz
        </button>
      </div>

      {state.error ? (
        <p className="alert" role="alert">
          {state.error}
        </p>
      ) : null}

      <div className="calendar-shell" aria-label="Tygodniowy kalendarz wizyt">
        <div className="calendar-grid calendar-header">
          <div className="time-column">
            <CalendarDays size={18} aria-hidden="true" />
          </div>
          {weekdays.map((day) => (
            <div className="day-heading" key={day}>
              {day}
            </div>
          ))}
        </div>

        <div className="calendar-content">
          <div className="calendar-body" style={{ height: calendarHeight }}>
            {hours.map((hour) => (
              <div className="calendar-grid calendar-row" key={hour}>
                <div className="time-column">{hour}</div>
                {weekdays.map((day) => (
                  <div className="empty-slot" key={`${day}-${hour}`} />
                ))}
              </div>
            ))}
          </div>

          <div className="calendar-events-layer" style={{ height: calendarHeight }}>
            <div className="time-column-spacer" />
            {weekdays.map((day, dayIndex) => (
              <div className="calendar-event-column" key={day}>
                {visibleEvents
                  .filter((placement) => placement.dayIndex === dayIndex)
                  .map((placement) => (
                    <article
                      className={placement.compact ? "calendar-event compact" : "calendar-event"}
                      key={placement.event.id}
                      title={`${placement.event.title}, ${formatTime(
                        placement.event.start,
                      )}-${formatTime(placement.event.end)}, ${placement.event.patient_label}`}
                      style={{
                        top: `${placement.top}px`,
                        height: `${placement.height}px`,
                      }}
                    >
                      <strong>{placement.event.title}</strong>
                      <span>
                        {formatTime(placement.event.start)}-{formatTime(placement.event.end)}
                      </span>
                      {!placement.compact ? <small>{placement.event.patient_label}</small> : null}
                    </article>
                  ))}
              </div>
            ))}
          </div>
        </div>

        {!state.loading && state.events.length === 0 ? (
          <div className="empty-calendar-state">
            <CalendarClock size={28} aria-hidden="true" />
            <h3>Brak wizyt</h3>
            <p>Wizyty demonstracyjne i nowe terminy będą renderowane tutaj z backendu.</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function toCalendarPlacement(event: CalendarEvent) {
  const start = new Date(event.start);
  const end = new Date(event.end);
  const dayIndex = start.getDay() - 1;

  if (dayIndex < 0 || dayIndex >= weekdays.length) {
    return null;
  }

  const minutesFromStart = (start.getHours() - dayStartHour) * 60 + start.getMinutes();
  const durationMinutes = Math.max(15, (end.getTime() - start.getTime()) / 60000);
  const pixelsPerMinute = calendarHeight / ((dayEndHour - dayStartHour) * 60);

  return {
    event,
    dayIndex,
    top: Math.max(0, minutesFromStart * pixelsPerMinute),
    height: Math.max(44, durationMinutes * pixelsPerMinute - 4),
    compact: durationMinutes <= 30,
  };
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("pl-PL", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function getPolishVisitCountLabel(count: number) {
  if (count === 1) {
    return "wizyta pobrana";
  }

  if (count >= 2 && count <= 4) {
    return "wizyty pobrane";
  }

  return "wizyt pobranych";
}
