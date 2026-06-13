import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.settings import Settings, get_settings
from app.models.ingestion import RagIngestionResponse
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextChunk:
    """One text chunk ready for embedding."""

    id: str
    content: str
    source_path: str
    heading: str | None = None


class RagIngestionService:
    """Build a Chroma RAG index from local scheduling documents."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def rebuild_index(self) -> RagIngestionResponse:
        """Rebuild the project-specific RAG collection from source documents."""
        documents = self._load_documents()
        chunks = [
            chunk
            for document_path, text in documents
            for chunk in _chunk_document(
                document_path=document_path,
                text=text,
                chunk_characters=self.settings.rag_chunk_characters,
                chunk_overlap=self.settings.rag_chunk_overlap,
            )
        ]

        if not chunks:
            raise RagDataNotReadyError(
                f"No RAG chunks found in document directory: {self.settings.rag_document_dir}"
            )

        self._store_chunks(chunks)
        logger.info(
            "RAG ingestion completed collection=%s documents=%s chunks=%s",
            self.settings.chroma_collection_name,
            len(documents),
            len(chunks),
        )
        return RagIngestionResponse(
            collection_name=self.settings.chroma_collection_name,
            document_count=len(documents),
            chunk_count=len(chunks),
        )

    def _load_documents(self) -> list[tuple[Path, str]]:
        document_dir = Path(self.settings.rag_document_dir)
        if not document_dir.exists():
            raise RagDataNotReadyError(f"RAG document directory does not exist: {document_dir}")

        documents: list[tuple[Path, str]] = []
        for path in sorted([*document_dir.glob("*.md"), *document_dir.glob("*.txt")]):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                documents.append((path, text))

        if not documents:
            raise RagDataNotReadyError(f"No RAG source documents found in: {document_dir}")

        return documents

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

        logger.info("Loading embedding model=%s for RAG ingestion", self.settings.embedding_model_name)
        model = SentenceTransformer(self.settings.embedding_model_name)
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


def _reset_collection(client: Any, collection_name: str) -> None:
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        logger.info("No existing Chroma collection to delete name=%s", collection_name)


def _chunk_document(
    document_path: Path,
    text: str,
    chunk_characters: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    heading = _first_heading(text)
    normalized_text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    chunks: list[TextChunk] = []
    start = 0
    index = 0

    while start < len(normalized_text):
        end = min(len(normalized_text), start + chunk_characters)
        content = normalized_text[start:end].strip()
        if content:
            chunks.append(
                TextChunk(
                    id=f"{document_path.stem}-{index}",
                    content=content,
                    source_path=str(document_path),
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
