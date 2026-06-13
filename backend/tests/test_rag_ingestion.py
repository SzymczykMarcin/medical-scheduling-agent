from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import rag
from app.core.settings import Settings
from app.main import app
from app.services.exceptions import RagDataNotReadyError
from app.services.rag_ingestion import RagIngestionService, _chunk_document


def test_chunk_document_preserves_heading_and_overlaps(tmp_path: Path) -> None:
    document_path = tmp_path / "rules.md"
    text = "# Respiratory rules\n" + "A" * 40 + "\n" + "B" * 40

    chunks = _chunk_document(
        document_path=document_path,
        text=text,
        chunk_characters=45,
        chunk_overlap=10,
    )

    assert len(chunks) > 1
    assert chunks[0].heading == "Respiratory rules"
    assert chunks[0].source_path == str(document_path)
    assert chunks[0].id == "rules-0"


def test_ingestion_reports_missing_document_directory(tmp_path: Path) -> None:
    service = RagIngestionService(
        Settings(
            rag_document_dir=str(tmp_path / "missing"),
            chroma_persist_dir=str(tmp_path / "chroma"),
        )
    )

    with pytest.raises(RagDataNotReadyError, match="does not exist"):
        service.rebuild_index()


def test_chroma_backend_ingestion_stores_vector_chunks(tmp_path: Path, monkeypatch) -> None:
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    (rag_dir / "rules.md").write_text("# Rules\nKonsultacja trwa 30 minut.", encoding="utf-8")
    stored_chunk_counts: list[int] = []

    def fake_store_chunks(self, chunks):
        stored_chunk_counts.append(len(chunks))

    monkeypatch.setattr(RagIngestionService, "_store_chunks", fake_store_chunks)
    service = RagIngestionService(
        Settings(
            rag_backend="chroma",
            rag_document_dir=str(rag_dir),
            chroma_persist_dir=str(tmp_path / "chroma"),
            chroma_collection_name="medical_scheduling_rules",
        )
    )

    response = service.rebuild_index()

    assert response.collection_name == "medical_scheduling_rules"
    assert response.document_count == 1
    assert response.chunk_count == 1
    assert stored_chunk_counts == [1]


def test_rag_ingestion_endpoint_maps_missing_data_to_bad_request(monkeypatch) -> None:
    class RejectingIngestionService:
        def rebuild_index(self):
            raise RagDataNotReadyError("No RAG source documents found.")

    monkeypatch.setattr(rag, "ingestion_service", RejectingIngestionService())
    client = TestClient(app)

    response = client.post("/api/rag/ingest")

    assert response.status_code == 400
    assert response.json() == {"detail": "No RAG source documents found."}
