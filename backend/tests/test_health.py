from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["runtime_profile"]
    assert body["llm_provider"] in {"llama-cpp", "ollama-http"}
    assert body["rag_backend"] in {"chroma", "bigquery-vector"}
    assert body["asr_provider"]
    assert "BIELIK_GGUF_PATH" not in body
    assert "OLLAMA_BASE_URL" not in body
