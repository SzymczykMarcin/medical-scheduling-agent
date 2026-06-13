import type { AppointmentResponse, CalendarEvent } from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? buildLocalApiBaseUrl();

function buildLocalApiBaseUrl() {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8097";
  }

  return `${window.location.protocol}//${window.location.hostname}:8097`;
}

export async function fetchCalendarEvents(signal?: AbortSignal): Promise<CalendarEvent[]> {
  const url = `${API_BASE_URL}/api/calendar/events`;
  const response = await safeFetch(url, { signal });

  if (!response.ok) {
    throw new Error(`Nie udało się pobrać wizyt z kalendarza. HTTP ${response.status}`);
  }

  return response.json();
}

export async function createAppointmentFromAudio(audio: Blob): Promise<AppointmentResponse> {
  const formData = new FormData();
  const url = `${API_BASE_URL}/api/voice/appointments`;
  formData.append("audio", audio, "recording.webm");

  console.info("[api] Sending appointment audio", {
    url,
    size: audio.size,
    type: audio.type || "unknown",
  });

  await verifyBackendReachable();

  const response = await safeFetch(url, {
    method: "POST",
    body: formData,
  });

  console.info("[api] Appointment response received", {
    url,
    status: response.status,
    ok: response.ok,
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(
      detail || `Nie udało się utworzyć wizyty na podstawie nagrania. HTTP ${response.status}`,
    );
  }

  return response.json();
}

async function verifyBackendReachable() {
  const healthUrl = `${API_BASE_URL}/health`;
  const response = await safeFetch(healthUrl);

  if (!response.ok) {
    throw new Error(`Backend health check failed. URL: ${healthUrl}. HTTP ${response.status}`);
  }
}

async function readErrorDetail(response: Response) {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string" ? payload.detail : null;
  } catch {
    return null;
  }
}

async function safeFetch(input: RequestInfo | URL, init?: RequestInit) {
  const url = input.toString();

  try {
    console.debug("[api] Fetch start", { url, method: init?.method ?? "GET" });
    return await fetch(input, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }

    const details = describeFetchError(error);
    console.error("[api] Fetch failed", { url, details, error });
    throw new Error(
      `Nie udało się połączyć z backendem. URL: ${url}. Szczegóły: ${details}`,
    );
  }
}

function describeFetchError(error: unknown) {
  if (error instanceof Error) {
    return `${error.name}: ${error.message}`;
  }

  return String(error);
}
