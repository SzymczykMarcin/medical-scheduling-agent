from datetime import date

import pytest

from app.core.settings import Settings
from app.models.rag import ConversationMessage, RetrievedPassage
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError
from app.services.rag import RagAnalysisService
from app.services.rag_prompting import SchedulingPromptBuilder
from app.services.rag_retrieval import FileKnowledgeBaseRetriever, KnowledgeBaseRetriever, ResilientKnowledgeBaseRetriever


class FakeRetriever:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        self.queries.append(f"{query}|{limit}")
        return [
            RetrievedPassage(
                content="Infekcja gardła i gorączka zwykle wymagają 30 minut konsultacji POZ.",
                source_path="rules.md",
                heading="Konsultacje podstawowe POZ",
            )
        ]


class FakeLlm:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[ConversationMessage] = []

    def generate(self, messages: list[ConversationMessage]) -> str:
        self.messages = messages
        return self.response


def test_rag_analysis_returns_structured_intent() -> None:
    retriever = FakeRetriever()
    llm = FakeLlm(
        """
        ```json
        {
          "visit_reason": "Ból gardła i gorączka",
          "procedure_hint": "Konsultacja POZ",
          "preferred_time": "wtorek po 10",
          "preferred_days": ["2026-06-11"],
          "preferred_time_windows": [
            {"date": "2026-06-11", "start_time": "10:00", "end_time": null}
          ],
          "excluded_days": [],
          "specific_datetime": "2026-06-11T10:00:00",
          "urgency": "standardowa",
          "duration_minutes": 30,
          "confidence": 0.82,
          "requires_human_callback": false,
          "explanation": "Reguła RAG wskazuje standardową konsultację POZ."
        }
        ```
        """
    )
    service = RagAnalysisService(
        settings=Settings(demo_mode=False, retrieval_limit=3),
        retriever=retriever,
        llm=llm,
    )

    intent = service.analyze(
        transcript="Boli mnie gardlo i mam goraczke. Prosze o wtorek po 10.",
        availability_summary="- 2026-06-09 10:30 - 12:00",
        today=date(2026, 6, 8),
    )

    assert intent.duration_minutes == 30
    assert intent.visit_reason == "Ból gardła i gorączka"
    assert intent.preferred_days == ["2026-06-09"]
    assert intent.preferred_time_windows[0].date is None
    assert intent.specific_datetime is None
    assert retriever.queries == ["Boli mnie gardlo i mam goraczke. Prosze o wtorek po 10.|3"]
    assert "Infekcja gardła" in llm.messages[-1].content
    assert "2026-06-09 10:30 - 12:00" in llm.messages[-1].content


def test_rag_analysis_rejects_invalid_llm_json() -> None:
    service = RagAnalysisService(
        settings=Settings(demo_mode=False),
        retriever=FakeRetriever(),
        llm=FakeLlm("not json"),
    )

    with pytest.raises(RagAnalysisError, match="JSON"):
        service.analyze_transcript("Potrzebuje wizyty.")


def test_prompt_builder_limits_context_size() -> None:
    builder = SchedulingPromptBuilder(max_context_characters=80)
    messages = builder.build_messages(
        transcript="Test transcript",
        retrieved_passages=[
            RetrievedPassage(content="krótka reguła", source_path="first.md"),
            RetrievedPassage(content="x" * 200, source_path="second.md"),
        ],
        availability_summary="- 2026-06-09 10:30 - 12:00",
        today="2026-06-08",
    )

    assert "krótka reguła" in messages[-1].content
    assert "2026-06-09 10:30 - 12:00" in messages[-1].content
    assert "second.md" not in messages[-1].content


def test_retriever_reports_missing_vector_store(tmp_path) -> None:
    retriever = KnowledgeBaseRetriever(
        Settings(
            chroma_persist_dir=str(tmp_path / "missing-chroma"),
            chroma_collection_name="medical_scheduling_rules",
        )
    )

    with pytest.raises(RagDataNotReadyError, match="not ready"):
        retriever.retrieve("query")


def test_retriever_wraps_chroma_client_startup_failure(tmp_path, monkeypatch) -> None:
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    (chroma_dir / "chroma.sqlite3").write_text("", encoding="utf-8")

    def failing_persistent_client(path: str):
        raise AttributeError("RustBindingsAPI object has no attribute bindings")

    import chromadb

    monkeypatch.setattr(chromadb, "PersistentClient", failing_persistent_client)
    retriever = KnowledgeBaseRetriever(
        Settings(
            chroma_persist_dir=str(chroma_dir),
            chroma_collection_name="medical_scheduling_rules",
        )
    )

    with pytest.raises(RagDataNotReadyError, match="could not be opened"):
        retriever.retrieve("query")


def test_resilient_retriever_uses_file_fallback_when_chroma_fails(tmp_path, monkeypatch) -> None:
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    (rag_dir / "rules.md").write_text(
        "# Konsultacje\nBól głowy i rutynowa konsultacja lekarza rodzinnego trwają 30 minut.",
        encoding="utf-8",
    )

    class FailingRetriever:
        def retrieve(self, query: str, limit: int | None = None):
            raise RagDataNotReadyError("Chroma unavailable.")

    settings = Settings(rag_document_dir=str(rag_dir), retrieval_limit=2)
    retriever = ResilientKnowledgeBaseRetriever(settings)
    retriever.primary = FailingRetriever()
    retriever.fallback = FileKnowledgeBaseRetriever(settings)

    passages = retriever.retrieve("Boli mnie głowa. Potrzebuję konsultacji.", limit=1)

    assert len(passages) == 1
    assert "Ból głowy" in passages[0].content
