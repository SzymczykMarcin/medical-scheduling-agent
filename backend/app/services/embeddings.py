import logging
from collections.abc import Callable
from typing import Any, Protocol

from app.core.settings import Settings, get_settings
from app.services.bielik import fetch_google_id_token, post_json
from app.services.exceptions import LlmGenerationError, RagAnalysisError

logger = logging.getLogger(__name__)


EmbeddingPost = Callable[[str, dict[str, Any], float, dict[str, str] | None], dict[str, Any]]


class EmbeddingProviderProtocol(Protocol):
    """Protocol for text embedding providers."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector for every input text."""


class EmbeddingService:
    """Generate embeddings with the configured provider."""

    def __init__(
        self,
        settings: Settings | None = None,
        post: EmbeddingPost | None = None,
        provider: EmbeddingProviderProtocol | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._provider = provider or create_embedding_provider(
            settings=self.settings,
            post=post,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for non-empty texts."""
        if not texts:
            return []
        return self._provider.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        """Return one embedding for a query."""
        embeddings = self.embed([text])
        if len(embeddings) != 1:
            raise RagAnalysisError("Embedding provider returned an unexpected result count.")
        return embeddings[0]


def create_embedding_provider(
    settings: Settings,
    post: EmbeddingPost | None = None,
) -> EmbeddingProviderProtocol:
    """Create the explicitly configured embedding provider."""
    if settings.embedding_provider == "sentence-transformers":
        return SentenceTransformerEmbeddingProvider(settings=settings)
    if settings.embedding_provider == "ollama-http":
        return OllamaHttpEmbeddingProvider(settings=settings, post=post or post_json)

    raise RagAnalysisError(f"Unsupported embedding provider: {settings.embedding_provider}")


class SentenceTransformerEmbeddingProvider:
    """Generate local embeddings with sentence-transformers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Any | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized local vectors."""
        vectors = self._get_model().encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RagAnalysisError("sentence-transformers is not installed.") from exc

            logger.info(
                "Loading embedding model=%s provider=sentence-transformers device=%s",
                self.settings.embedding_model_name,
                self.settings.embedding_device,
            )
            self._model = SentenceTransformer(
                self.settings.embedding_model_name,
                device=self.settings.embedding_device,
            )
            logger.info("Embedding model loaded successfully provider=sentence-transformers.")
        return self._model


class OllamaHttpEmbeddingProvider:
    """Generate embeddings through an Ollama-compatible HTTP API."""

    def __init__(self, settings: Settings, post: EmbeddingPost) -> None:
        if not settings.embedding_base_url:
            raise RagAnalysisError("EMBEDDING_BASE_URL is required for Ollama embeddings.")
        self.settings = settings
        self._post = post

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate vectors through Ollama /api/embed."""
        payload = {
            "model": self.settings.embedding_model_name,
            "input": texts if len(texts) > 1 else texts[0],
        }
        url = _join_url(self.settings.embedding_base_url or "", "/api/embed")
        logger.info(
            "Starting embedding request provider=ollama-http base_url=%s model=%s texts=%s",
            self.settings.embedding_base_url,
            self.settings.embedding_model_name,
            len(texts),
        )

        try:
            response = self._post(
                url,
                payload,
                self.settings.embedding_timeout_seconds,
                self._auth_headers(),
            )
        except LlmGenerationError as exc:
            raise RagAnalysisError("Embedding Ollama request failed.") from exc

        embeddings = _extract_ollama_embeddings(response)
        if len(embeddings) != len(texts):
            raise RagAnalysisError(
                "Embedding provider returned an unexpected number of vectors."
            )
        logger.info(
            "Embedding request completed provider=ollama-http model=%s texts=%s",
            self.settings.embedding_model_name,
            len(texts),
        )
        return embeddings

    def _auth_headers(self) -> dict[str, str] | None:
        if self.settings.embedding_auth_mode == "none":
            return None
        if self.settings.embedding_auth_mode == "google-id-token":
            token = fetch_google_id_token(self.settings.embedding_base_url or "")
            return {"Authorization": f"Bearer {token}"}
        raise RagAnalysisError(
            f"Unsupported embedding auth mode: {self.settings.embedding_auth_mode}"
        )


def _extract_ollama_embeddings(response: dict[str, Any]) -> list[list[float]]:
    raw_embeddings = response.get("embeddings")
    if not isinstance(raw_embeddings, list):
        raise RagAnalysisError("Ollama embedding response does not contain embeddings.")

    embeddings: list[list[float]] = []
    for vector in raw_embeddings:
        if not isinstance(vector, list) or not all(_is_number(value) for value in vector):
            raise RagAnalysisError("Ollama embedding response has invalid vector data.")
        embeddings.append([float(value) for value in vector])
    return embeddings


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
