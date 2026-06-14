import logging
from pathlib import Path
from typing import Any, Protocol

from app.core.settings import Settings, get_settings
from app.models.rag import RetrievedPassage
from app.services.embeddings import EmbeddingService
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

            logger.info(
                "Loading embedding model=%s device=%s",
                self.settings.embedding_model_name,
                self.settings.embedding_device,
            )
            self._embedding_model = SentenceTransformer(
                self.settings.embedding_model_name,
                device=self.settings.embedding_device,
            )
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
    """Retrieve scheduling guidance from BigQuery Vector Search."""

    def __init__(
        self,
        settings: Settings | None = None,
        bigquery_client: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        embedding_model: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._bigquery_client = bigquery_client
        self._embedding_service = embedding_service
        self._legacy_embedding_model = embedding_model

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Return passages from a cloud vector store when configured."""
        selected_limit = limit or self.settings.retrieval_limit
        logger.info(
            "Starting RAG retrieval backend=bigquery-vector query_chars=%s limit=%s "
            "dataset=%s table=%s",
            len(query),
            selected_limit,
            self.settings.bigquery_dataset_id,
            self.settings.bigquery_table_id,
        )
        if not self.settings.bigquery_project_id:
            raise RagDataNotReadyError(
                "BIGQUERY_PROJECT_ID is required when RAG_BACKEND=bigquery-vector."
            )

        query_embedding = self._embed_query(query)
        rows = self._run_vector_search(query_embedding=query_embedding, limit=selected_limit)
        passages = [_map_bigquery_row(row) for row in rows]
        logger.info(
            "RAG retrieval completed backend=bigquery-vector passages=%s table=%s.%s.%s",
            len(passages),
            self.settings.bigquery_project_id,
            self.settings.bigquery_dataset_id,
            self.settings.bigquery_table_id,
        )
        return passages

    def _get_embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService(self.settings)
        return self._embedding_service

    def _embed_query(self, query: str) -> list[float]:
        if self._legacy_embedding_model is not None:
            vector = self._legacy_embedding_model.encode(query, normalize_embeddings=True)
            return vector.tolist()
        return self._get_embedding_service().embed_query(query)

    def _get_bigquery_client(self) -> Any:
        if self._bigquery_client is None:
            try:
                from google.cloud import bigquery
            except ImportError as exc:
                raise RagAnalysisError(
                    "google-cloud-bigquery is required for RAG_BACKEND=bigquery-vector."
                ) from exc
            self._bigquery_client = bigquery.Client(project=self.settings.bigquery_project_id)
        return self._bigquery_client

    def _build_job_config(self, query_embedding: list[float], limit: int) -> Any:
        try:
            from google.cloud import bigquery
        except ImportError:
            return {"query_embedding": query_embedding, "limit": limit}
        return bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("query_embedding", "FLOAT64", query_embedding),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

    def _run_vector_search(self, query_embedding: list[float], limit: int) -> list[Any]:
        table_ref = (
            f"`{self.settings.bigquery_project_id}."
            f"{self.settings.bigquery_dataset_id}.{self.settings.bigquery_table_id}`"
        )
        sql = f"""
        SELECT
          base.id AS id,
          base.content AS content,
          base.source_path AS source_path,
          base.heading AS heading,
          distance
        FROM VECTOR_SEARCH(
          TABLE {table_ref},
          'embedding',
          (SELECT @query_embedding AS embedding),
          top_k => @limit
        )
        ORDER BY distance ASC
        """
        try:
            job = self._get_bigquery_client().query(
                sql,
                job_config=self._build_job_config(query_embedding, limit),
            )
            return list(job.result())
        except Exception as exc:
            logger.exception("BigQuery vector retrieval failed.")
            raise RagAnalysisError("Could not retrieve BigQuery RAG context.") from exc


def _map_bigquery_row(row: Any) -> RetrievedPassage:
    return RetrievedPassage(
        content=str(_read_row_field(row, "content", "")),
        source_path=str(_read_row_field(row, "source_path", "bigquery")),
        distance=_read_optional_float(row, "distance"),
        heading=str(_read_row_field(row, "heading", "")) or None,
        section_slug=str(_read_row_field(row, "id", "")) or None,
    )


def _read_row_field(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _read_optional_float(row: Any, key: str) -> float | None:
    value = _read_row_field(row, key)
    return float(value) if value is not None else None


def _source_labels(passages: list[RetrievedPassage]) -> list[str]:
    return [
        passage.heading
        or Path(passage.source_path).name
        or passage.section_slug
        or "unknown"
        for passage in passages
    ]

