import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.settings import Settings, get_settings
from app.models.ingestion import RagIngestionResponse
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError
from app.services.embeddings import EmbeddingService
from app.services.medical_rules import MedicalRuleSourceLoader, SourceDocument

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextChunk:
    """One text chunk ready for embedding."""

    id: str
    content: str
    source_path: str
    heading: str | None = None


class RagIngestionService:
    """Prepare RAG source documents for the configured backend."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def rebuild_index(self) -> RagIngestionResponse:
        """Rebuild the project-specific RAG collection from source documents."""
        documents = self._load_documents()
        chunks = [
            chunk
            for document in documents
            for chunk in _chunk_document(
                document=document,
                chunk_characters=self.settings.rag_chunk_characters,
                chunk_overlap=self.settings.rag_chunk_overlap,
            )
        ]

        if not chunks:
            raise RagDataNotReadyError(
                f"No RAG chunks found in document directory: {self.settings.rag_document_dir}"
            )

        if self.settings.rag_backend == "chroma":
            self._store_chunks(chunks)
            collection_name = self.settings.chroma_collection_name
        elif self.settings.rag_backend == "bigquery-vector":
            self._store_bigquery_chunks(chunks)
            collection_name = (
                f"{self.settings.bigquery_dataset_id}.{self.settings.bigquery_table_id}"
            )
        else:
            raise RagDataNotReadyError(f"Unsupported RAG backend: {self.settings.rag_backend}")

        logger.info(
            "RAG ingestion completed backend=%s collection=%s documents=%s chunks=%s",
            self.settings.rag_backend,
            collection_name,
            len(documents),
            len(chunks),
        )
        return RagIngestionResponse(
            collection_name=collection_name,
            document_count=len(documents),
            chunk_count=len(chunks),
        )

    def _load_documents(self) -> list[SourceDocument]:
        return MedicalRuleSourceLoader(Path(self.settings.rag_document_dir)).load_documents()

    def _store_chunks(self, chunks: list[TextChunk]) -> None:
        try:
            from chromadb import PersistentClient
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RagAnalysisError("chromadb and sentence-transformers are required for RAG ingestion.") from exc

        chroma_dir = Path(self.settings.chroma_persist_dir)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        client = PersistentClient(path=str(chroma_dir))
        _reset_collection(client, self.settings.chroma_collection_name)
        collection = client.get_or_create_collection(name=self.settings.chroma_collection_name)

        logger.info(
            "Loading embedding model=%s device=%s for RAG ingestion",
            self.settings.embedding_model_name,
            self.settings.embedding_device,
        )
        model = SentenceTransformer(
            self.settings.embedding_model_name,
            device=self.settings.embedding_device,
        )
        documents = [chunk.content for chunk in chunks]
        embeddings = model.encode(documents, normalize_embeddings=True).tolist()
        collection.add(
            ids=[chunk.id for chunk in chunks],
            documents=documents,
            embeddings=embeddings,
            metadatas=[
                {
                    "source_path": chunk.source_path,
                    "heading": chunk.heading or "",
                }
                for chunk in chunks
            ],
        )

    def _store_bigquery_chunks(self, chunks: list[TextChunk]) -> None:
        if not self.settings.bigquery_project_id:
            raise RagDataNotReadyError(
                "BIGQUERY_PROJECT_ID is required when RAG_BACKEND=bigquery-vector."
            )
        try:
            from google.cloud import bigquery
        except ImportError as exc:
            raise RagAnalysisError(
                "google-cloud-bigquery is required for BigQuery RAG ingestion."
            ) from exc

        table_id = (
            f"{self.settings.bigquery_project_id}."
            f"{self.settings.bigquery_dataset_id}.{self.settings.bigquery_table_id}"
        )
        client = bigquery.Client(project=self.settings.bigquery_project_id)
        dataset_id = f"{self.settings.bigquery_project_id}.{self.settings.bigquery_dataset_id}"
        client.create_dataset(bigquery.Dataset(dataset_id), exists_ok=True)
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("content", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_path", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("heading", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
        ]
        client.delete_table(table_id, not_found_ok=True)
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table, exists_ok=True)

        logger.info(
            "Generating embeddings for BigQuery RAG ingestion provider=%s model=%s chunks=%s",
            self.settings.embedding_provider,
            self.settings.embedding_model_name,
            len(chunks),
        )
        embeddings = EmbeddingService(self.settings).embed([chunk.content for chunk in chunks])
        rows = [
            {
                "id": chunk.id,
                "content": chunk.content,
                "source_path": chunk.source_path,
                "heading": chunk.heading or "",
                "embedding": embedding,
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            raise RagAnalysisError(f"BigQuery RAG ingestion failed: {errors}")


def _reset_collection(client: Any, collection_name: str) -> None:
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        logger.info("No existing Chroma collection to delete name=%s", collection_name)


def _chunk_document(
    document: SourceDocument,
    chunk_characters: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    heading = document.heading or _first_heading(document.text)
    document_id = document.document_id or document.path.stem
    normalized_text = "\n".join(line.rstrip() for line in document.text.splitlines()).strip()
    chunks: list[TextChunk] = []
    start = 0
    index = 0

    while start < len(normalized_text):
        end = min(len(normalized_text), start + chunk_characters)
        content = normalized_text[start:end].strip()
        if content:
            chunks.append(
                TextChunk(
                    id=f"{document_id}-{index}",
                    content=content,
                    source_path=str(document.path),
                    heading=heading,
                )
            )
            index += 1

        if end >= len(normalized_text):
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None
