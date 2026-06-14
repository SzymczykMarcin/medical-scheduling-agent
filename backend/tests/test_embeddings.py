import pytest

from app.core.settings import Settings
from app.services.embeddings import EmbeddingService
from app.services.exceptions import RagAnalysisError


def test_ollama_embedding_service_posts_to_embed_endpoint() -> None:
    calls: list[tuple[str, dict, float, dict[str, str] | None]] = []

    def fake_post(url: str, payload: dict, timeout: float, headers: dict[str, str] | None):
        calls.append((url, payload, timeout, headers))
        return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    service = EmbeddingService(
        Settings(
            embedding_provider="ollama-http",
            embedding_base_url="https://embedding.example.test",
            embedding_model_name="embeddinggemma:latest",
            embedding_auth_mode="none",
            embedding_timeout_seconds=15,
        ),
        post=fake_post,
    )

    embeddings = service.embed(["pierwszy tekst", "drugi tekst"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    assert calls == [
        (
            "https://embedding.example.test/api/embed",
            {"model": "embeddinggemma:latest", "input": ["pierwszy tekst", "drugi tekst"]},
            15,
            None,
        )
    ]


def test_ollama_embedding_service_rejects_wrong_vector_count() -> None:
    def fake_post(url: str, payload: dict, timeout: float, headers: dict[str, str] | None):
        return {"embeddings": [[0.1, 0.2]]}

    service = EmbeddingService(
        Settings(
            embedding_provider="ollama-http",
            embedding_base_url="https://embedding.example.test",
            embedding_auth_mode="none",
        ),
        post=fake_post,
    )

    with pytest.raises(RagAnalysisError, match="unexpected number"):
        service.embed(["pierwszy tekst", "drugi tekst"])


def test_cloud_bigquery_settings_require_embedding_service_url() -> None:
    with pytest.raises(ValueError, match="EMBEDDING_BASE_URL"):
        Settings(
            runtime_profile="cloud-run",
            rag_backend="bigquery-vector",
            bigquery_project_id="demo-project",
            embedding_provider="ollama-http",
            embedding_base_url=None,
        )
