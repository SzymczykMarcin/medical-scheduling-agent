from datetime import date

from fastapi.testclient import TestClient

from app.api import debug
from app.main import app
from app.models.rag import ConversationMessage, RetrievedPassage
from app.services.debug_analysis import AppointmentDebugAnalysisService


class FakeRetriever:
    def __init__(self, passages: list[RetrievedPassage] | None = None) -> None:
        self.passages = passages or [
            RetrievedPassage(
                content="Konsultacja neurologiczna zwykle trwa 60 minut.",
                source_path="rules.md",
                heading="Neurologia",
            )
        ]
        self.queries: list[str] = []

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        self.queries.append(f"{query}|{limit}")
        return self.passages


class FakeLlm:
    def __init__(self, rag_response: str) -> None:
        self.rag_response = rag_response
        self.messages: list[list[ConversationMessage]] = []

    def generate(self, messages: list[ConversationMessage]) -> str:
        self.messages.append(messages)
        if len(self.messages) == 1:
            return "Direct summary"
        return self.rag_response


def _valid_intent_json(**overrides) -> str:
    payload = {
        "visit_reason": "Bol glowy",
        "procedure_hint": "Konsultacja neurologiczna",
        "preferred_time": "wtorek po 10",
        "preferred_days": ["2026-06-09"],
        "preferred_time_windows": [
            {"date": "2026-06-09", "start_time": "10:00", "end_time": "12:00"}
        ],
        "excluded_days": [],
        "specific_datetime": None,
        "urgency": "standardowa",
        "duration_minutes": 60,
        "confidence": 0.9,
        "requires_human_callback": False,
        "explanation": "Reguly wskazuja konsultacje neurologiczna.",
    }
    payload.update(overrides)

    import json

    return json.dumps(payload)


def test_debug_analysis_returns_complete_success_response() -> None:
    retriever = FakeRetriever()
    llm = FakeLlm(_valid_intent_json())
    service = AppointmentDebugAnalysisService(retriever=retriever, llm=llm)

    response = service.analyze(
        transcript="Boli mnie glowa, prosze o wtorek po 10.",
        today=date(2026, 6, 8),
    )

    assert response.status == "completed"
    assert response.failed_stage is None
    assert response.direct_bielik_output == "Direct summary"
    assert response.retrieved_context[0].heading == "Neurologia"
    assert response.rag_bielik_raw_output is not None
    assert response.validated_intent is not None
    assert response.validated_intent.duration_minutes == 60
    assert response.scheduler_result is not None
    assert response.scheduler_result.status == "scheduled"
    assert response.scheduler_result.event is not None
    assert response.sms_text is not None
    assert retriever.queries == ["Boli mnie glowa, prosze o wtorek po 10.|4"]


def test_debug_analysis_reports_validation_failure_for_invalid_json() -> None:
    service = AppointmentDebugAnalysisService(
        retriever=FakeRetriever(),
        llm=FakeLlm("not-json"),
    )

    response = service.analyze(
        transcript="Potrzebuje wizyty.",
        today=date(2026, 6, 8),
    )

    assert response.status == "failed"
    assert response.failed_stage == "validation"
    assert response.error_message is not None
    assert response.direct_bielik_output == "Direct summary"
    assert response.retrieved_context
    assert response.scheduler_result is None
    assert response.sms_text is None


def test_debug_analysis_returns_scheduler_callback_result() -> None:
    service = AppointmentDebugAnalysisService(
        retriever=FakeRetriever(),
        llm=FakeLlm(_valid_intent_json(confidence=0.1)),
    )

    response = service.analyze(
        transcript="Nie wiem kiedy moge przyjsc.",
        today=date(2026, 6, 8),
    )

    assert response.status == "completed"
    assert response.scheduler_result is not None
    assert response.scheduler_result.status == "needs_callback"
    assert response.scheduler_result.event is None
    assert response.sms_text is not None


def test_debug_endpoint_uses_configured_service(monkeypatch) -> None:
    service = AppointmentDebugAnalysisService(
        retriever=FakeRetriever(),
        llm=FakeLlm(_valid_intent_json()),
    )
    monkeypatch.setattr(debug, "debug_analysis_service", service)
    client = TestClient(app)

    response = client.post(
        "/api/debug/appointment-analysis",
        json={
            "transcript": "Boli mnie glowa, prosze o wtorek po 10.",
            "today": "2026-06-08",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["direct_bielik_output"] == "Direct summary"
    assert body["retrieved_context"][0]["heading"] == "Neurologia"
    assert body["scheduler_result"]["status"] == "scheduled"


def test_prewarm_endpoint_reports_loaded_components(monkeypatch) -> None:
    calls: list[str] = []

    class FakeTranscriptionService:
        def prewarm_model(self) -> None:
            calls.append("asr")

    class FakeLlmService:
        def generate(self, messages) -> str:
            calls.append("bielik")
            return "gotowe"

    class FakeEmbeddingService:
        def embed_query(self, text: str) -> list[float]:
            calls.append("embedding")
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(debug, "transcription_service", FakeTranscriptionService())
    monkeypatch.setattr(debug, "embedding_service", FakeEmbeddingService())
    monkeypatch.setattr(debug, "llm_service", FakeLlmService())
    client = TestClient(app)

    response = client.post("/api/debug/prewarm")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert [component["name"] for component in body["components"]] == [
        "asr",
        "embedding",
        "bielik",
    ]
    assert calls == ["asr", "embedding", "bielik"]


def test_prewarm_endpoint_fails_visibly(monkeypatch) -> None:
    class FailingTranscriptionService:
        def prewarm_model(self) -> None:
            raise RuntimeError("ASR download failed")

    class FakeLlmService:
        def generate(self, messages) -> str:
            return "gotowe"

    class FakeEmbeddingService:
        def embed_query(self, text: str) -> list[float]:
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(debug, "transcription_service", FailingTranscriptionService())
    monkeypatch.setattr(debug, "embedding_service", FakeEmbeddingService())
    monkeypatch.setattr(debug, "llm_service", FakeLlmService())
    client = TestClient(app)

    response = client.post("/api/debug/prewarm")

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "failed"
    assert body["components"][0]["name"] == "asr"
    assert body["components"][0]["status"] == "failed"
    assert "ASR download failed" in body["components"][0]["error_message"]
