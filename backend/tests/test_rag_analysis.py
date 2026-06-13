from datetime import date

import pytest

from app.core.settings import Settings
from app.models.rag import ConversationMessage, RetrievedPassage
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError
from app.services.rag import RagAnalysisService
from app.services.rag_prompting import SchedulingPromptBuilder
from app.services.rag_retrieval import (
    BigQueryVectorKnowledgeBaseRetriever,
    ChromaKnowledgeBaseRetriever,
    create_knowledge_base_retriever,
)


class FakeRetriever:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        self.queries.append(f"{query}|{limit}")
        return [
            RetrievedPassage(
                content="Respiratory infection usually requires a 30 minute appointment.",
                source_path="rules.md",
                heading="Primary care consultations",
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
          "visit_reason": "Bol gardla i goraczka",
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
          "explanation": "Regula RAG wskazuje standardowa konsultacje POZ."
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
    assert intent.visit_reason == "Bol gardla i goraczka"
    assert intent.preferred_days == ["2026-06-09"]
    assert intent.preferred_time_windows[0].date is None
    assert intent.specific_datetime is None
    assert retriever.queries == ["Boli mnie gardlo i mam goraczke. Prosze o wtorek po 10.|3"]
    assert "Respiratory infection" in llm.messages[-1].content
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
            RetrievedPassage(content="short rule", source_path="first.md"),
            RetrievedPassage(content="x" * 200, source_path="second.md"),
        ],
        availability_summary="- 2026-06-09 10:30 - 12:00",
        today="2026-06-08",
    )

    assert "short rule" in messages[-1].content
    assert "2026-06-09 10:30 - 12:00" in messages[-1].content
    assert "second.md" not in messages[-1].content


def test_retriever_reports_missing_vector_store(tmp_path) -> None:
    retriever = ChromaKnowledgeBaseRetriever(
        Settings(
            rag_backend="chroma",
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
    retriever = ChromaKnowledgeBaseRetriever(
        Settings(
            rag_backend="chroma",
            chroma_persist_dir=str(chroma_dir),
            chroma_collection_name="medical_scheduling_rules",
        )
    )

    with pytest.raises(RagDataNotReadyError, match="could not be opened"):
        retriever.retrieve("query")


def test_retriever_factory_selects_chroma_backend(tmp_path) -> None:
    retriever = create_knowledge_base_retriever(
        Settings(rag_backend="chroma", chroma_persist_dir=str(tmp_path / "chroma"))
    )

    assert isinstance(retriever, ChromaKnowledgeBaseRetriever)


def test_retriever_factory_selects_bigquery_vector_backend() -> None:
    retriever = create_knowledge_base_retriever(
        Settings(rag_backend="bigquery-vector", bigquery_project_id="demo-project")
    )

    assert isinstance(retriever, BigQueryVectorKnowledgeBaseRetriever)


def test_chroma_retriever_queries_vector_store_with_embedding(tmp_path) -> None:
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    (chroma_dir / "chroma.sqlite3").write_text("", encoding="utf-8")

    class FakeEmbedding:
        def encode(self, query: str, normalize_embeddings: bool):
            assert query == "headache consultation"
            assert normalize_embeddings is True
            return FakeVector([0.1, 0.2, 0.3])

    class FakeVector(list):
        def tolist(self):
            return list(self)

    class FakeCollection:
        def __init__(self) -> None:
            self.n_results: int | None = None

        def query(self, query_embeddings, n_results: int, include):
            assert query_embeddings == [[0.1, 0.2, 0.3]]
            assert include == ["documents", "metadatas", "distances"]
            self.n_results = n_results
            return {
                "documents": [["Neurology consultation usually takes 60 minutes."]],
                "metadatas": [[{"source_path": "rules.md", "heading": "Neurology"}]],
                "distances": [[0.12]],
            }

    retriever = ChromaKnowledgeBaseRetriever(
        Settings(
            rag_backend="chroma",
            chroma_persist_dir=str(chroma_dir),
            chroma_collection_name="medical_scheduling_rules",
        )
    )
    collection = FakeCollection()
    retriever._embedding_model = FakeEmbedding()
    retriever._collection = collection

    passages = retriever.retrieve("headache consultation", limit=1)

    assert collection.n_results == 1
    assert passages[0].content == "Neurology consultation usually takes 60 minutes."
    assert passages[0].heading == "Neurology"
    assert passages[0].distance == 0.12


def test_chroma_backend_does_not_fall_back_when_store_is_missing(tmp_path) -> None:
    retriever = create_knowledge_base_retriever(
        Settings(
            rag_backend="chroma",
            chroma_persist_dir=str(tmp_path / "missing-chroma"),
        )
    )

    with pytest.raises(RagDataNotReadyError, match="not ready"):
        retriever.retrieve("consultation", limit=1)


def test_bigquery_vector_backend_reports_not_implemented_with_project_id() -> None:
    retriever = BigQueryVectorKnowledgeBaseRetriever(
        Settings(rag_backend="bigquery-vector", bigquery_project_id="demo-project")
    )

    with pytest.raises(RagDataNotReadyError, match="not implemented"):
        retriever.retrieve("consultation")
