from fastapi.testclient import TestClient

from app.main import app


def test_calendar_events_endpoint_returns_seed_appointments() -> None:
    client = TestClient(app)

    response = client.get("/api/calendar/events")

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 16
    assert events[0]["id"] == "seed-1"
    assert events[0]["duration_minutes"] == 30
    assert "start" in events[0]
    assert "end" in events[0]
