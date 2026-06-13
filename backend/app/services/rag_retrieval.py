import logging
from pathlib import Path
from typing import Any, Protocol

from app.core.settings import Settings, get_settings
from app.models.rag import RetrievedPassage
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError

logger = logging.getLogger(__name__)


class RetrieverProtocol(Protocol):
    """Common interface for RAG retrieval backends."""

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Return passages relevant to a transcript or user query."""


def create_knowledge_base_retriever(settings: Settings | None = None) -> RetrieverProtocol:
    """Create the explicitly configured RAG retrieval backend."""
    resolved_settings = settings or get_settings()
    if resolved_settings.rag_backend == "chroma":
        return ChromaKnowledgeBaseRetriever(resolved_settings)
    if resolved_settings.rag_backend == "bigquery-vector":
        return BigQueryVectorKnowledgeBaseRetriever(resolved_settings)

    raise RagDataNotReadyError(f"Unsupported RAG backend: {resolved_settings.rag_backend}")


class ChromaKnowledgeBaseRetriever:
    """Retrieve scheduling guidance from the local Chroma vector store."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._embedding_model: Any | None = None
        self._client: Any | None = None
        self._collection: Any | None = None

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Return passages relevant to a transcript or user query."""
        selected_limit = limit or self.settings.retrieval_limit
        logger.info(
            "Starting RAG retrieval backend=chroma query_chars=%s limit=%s collection=%s",
            len(query),
            selected_limit,
            self.settings.chroma_collection_name,
        )
        self._ensure_vector_store_exists()
        collection = self._get_collection()
        query_embedding = self._get_embedding_model().encode(
            query,
            normalize_embeddings=True,
        ).tolist()

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=selected_limit,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.exception("Chroma retrieval failed.")
            raise RagAnalysisError("Could not retrieve RAG context.") from exc

        passages = _map_chroma_results(results)
        logger.info(
            "RAG retrieval completed backend=chroma passages=%s sources=%s collection=%s",
            len(passages),
            _source_labels(passages),
            self.settings.chroma_collection_name,
        )
        return passages

    def _ensure_vector_store_exists(self) -> None:
        chroma_dir = Path(self.settings.chroma_persist_dir)
        sqlite_path = chroma_dir / "chroma.sqlite3"
        if not sqlite_path.exists():
            raise RagDataNotReadyError(
                f"RAG vector store is not ready. Expected Chroma database at {sqlite_path}."
            )

    def _get_embedding_model(self) -> Any:
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RagAnalysisError("sentence-transformers is not installed.") from exc

            logger.info("Loading embedding model=%s", self.settings.embedding_model_name)
            self._embedding_model = SentenceTransformer(self.settings.embedding_model_name)
            logger.info("Embedding model loaded successfully.")

        return self._embedding_model

    def _get_collection(self) -> Any:
        if self._collection is None:
            try:
                from chromadb import PersistentClient
            except ImportError as exc:
                raise RagAnalysisError("chromadb is not installed.") from exc

            if self._client is None:
                try:
                    self._client = PersistentClient(path=self.settings.chroma_persist_dir)
                except Exception as exc:
                    logger.exception(
                        "Could not open Chroma persistent client path=%s",
                        self.settings.chroma_persist_dir,
                    )
                    raise RagDataNotReadyError(
                        f"RAG vector store could not be opened: {self.settings.chroma_persist_dir}"
                    ) from exc
            try:
                self._collection = self._client.get_collection(
                    name=self.settings.chroma_collection_name,
                )
            except Exception as exc:
                logger.exception(
                    "Could not open Chroma collection name=%s",
                    self.settings.chroma_collection_name,
                )
                raise RagDataNotReadyError(
                    f"RAG collection does not exist: {self.settings.chroma_collection_name}"
                ) from exc

        return self._collection


def _map_chroma_results(results: dict[str, Any]) -> list[RetrievedPassage]:
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    passages: list[RetrievedPassage] = []

    for document, metadata, distance in zip(documents, metadatas, distances):
        safe_metadata = metadata or {}
        passages.append(
            RetrievedPassage(
                content=str(document),
                source_path=str(safe_metadata.get("source_path", "unknown")),
                distance=float(distance) if distance is not None else None,
                heading=str(safe_metadata.get("heading") or "") or None,
                section_slug=str(safe_metadata.get("section_slug") or "") or None,
            )
        )

    return passages


class BigQueryVectorKnowledgeBaseRetriever:
    """Extension point for cloud vector retrieval through BigQuery Vector Search."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Return passages from a cloud vector store when configured."""
        logger.info(
            "Starting RAG retrieval backend=bigquery-vector query_chars=%s limit=%s "
            "dataset=%s table=%s",
            len(query),
            limit or self.settings.retrieval_limit,
            self.settings.bigquery_dataset_id,
            self.settings.bigquery_table_id,
        )
        if not self.settings.bigquery_project_id:
            raise RagDataNotReadyError(
                "BIGQUERY_PROJECT_ID is required when RAG_BACKEND=bigquery-vector."
            )
        raise RagDataNotReadyError("BigQuery vector retrieval is not implemented yet.")


def _source_labels(passages: list[RetrievedPassage]) -> list[str]:
    return [
        passage.heading
        or Path(passage.source_path).name
        or passage.section_slug
        or "unknown"
        for passage in passages
    ]

