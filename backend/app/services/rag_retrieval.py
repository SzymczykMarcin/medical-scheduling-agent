import logging
from pathlib import Path
from typing import Any

from app.core.settings import Settings, get_settings
from app.models.rag import RetrievedPassage
from app.services.exceptions import RagAnalysisError, RagDataNotReadyError

logger = logging.getLogger(__name__)


class KnowledgeBaseRetriever:
    """Retrieve scheduling guidance from the local Chroma vector store."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._embedding_model: Any | None = None
        self._client: Any | None = None
        self._collection: Any | None = None

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Return passages relevant to a transcript or user query."""
        self._ensure_vector_store_exists()
        collection = self._get_collection()
        query_embedding = self._get_embedding_model().encode(
            query,
            normalize_embeddings=True,
        ).tolist()

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit or self.settings.retrieval_limit,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.exception("Chroma retrieval failed.")
            raise RagAnalysisError("Could not retrieve RAG context.") from exc

        passages = _map_chroma_results(results)
        logger.info(
            "RAG retrieval completed passages=%s collection=%s",
            len(passages),
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


class FileKnowledgeBaseRetriever:
    """Retrieve RAG context directly from local markdown files when Chroma is unavailable."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._passages: list[RetrievedPassage] | None = None

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Return relevant passages using deterministic keyword scoring."""
        passages = self._load_passages()
        scored = [
            (score, index, passage)
            for index, passage in enumerate(passages)
            if (score := _keyword_score(query, passage.content)) > 0
        ]

        if not scored:
            scored = [(0, index, passage) for index, passage in enumerate(passages)]

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = [passage for _score, _index, passage in scored[: limit or self.settings.retrieval_limit]]
        logger.info("File RAG retrieval completed passages=%s", len(selected))
        return selected

    def _load_passages(self) -> list[RetrievedPassage]:
        if self._passages is None:
            document_dir = Path(self.settings.rag_document_dir)
            if not document_dir.exists():
                raise RagDataNotReadyError(f"RAG document directory does not exist: {document_dir}")

            passages: list[RetrievedPassage] = []
            for path in sorted([*document_dir.glob("*.md"), *document_dir.glob("*.txt")]):
                text = path.read_text(encoding="utf-8").strip()
                if not text:
                    continue
                passages.extend(_split_document_into_passages(path, text))

            if not passages:
                raise RagDataNotReadyError(f"No RAG source documents found in: {document_dir}")

            self._passages = passages

        return self._passages


class ResilientKnowledgeBaseRetriever:
    """Use Chroma first and fall back to file-based retrieval for local demo robustness."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.primary = KnowledgeBaseRetriever(self.settings)
        self.fallback = FileKnowledgeBaseRetriever(self.settings)

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedPassage]:
        """Return RAG passages without failing the appointment flow on Chroma issues."""
        if self.settings.rag_backend == "file":
            return self.fallback.retrieve(query, limit=limit)

        try:
            return self.primary.retrieve(query, limit=limit)
        except Exception as exc:
            logger.warning("Chroma RAG unavailable; using file RAG fallback. reason=%s", exc)
            return self.fallback.retrieve(query, limit=limit)


def _split_document_into_passages(path: Path, text: str) -> list[RetrievedPassage]:
    sections: list[RetrievedPassage] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append(
                RetrievedPassage(
                    content=content,
                    source_path=str(path),
                    heading=current_heading,
                    distance=None,
                    section_slug=_slugify(current_heading or path.stem),
                )
            )

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            current_heading = line.lstrip("#").strip() or None
            current_lines = [line]
        else:
            current_lines.append(line)

    flush()
    return sections


def _keyword_score(query: str, content: str) -> int:
    query_tokens = _tokens(query)
    content_tokens = set(_tokens(content))
    return sum(1 for token in query_tokens if token in content_tokens)


def _tokens(value: str) -> list[str]:
    import re

    return [token for token in re.findall(r"[\wąćęłńóśźż]+", value.lower()) if len(token) >= 3]


def _slugify(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
