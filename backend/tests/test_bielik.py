import pytest

from app.core.settings import Settings
from app.models.rag import ConversationMessage
from app.services.bielik import (
    BielikLlmService,
    OllamaHttpBielikProvider,
    create_bielik_provider,
    fetch_google_id_token,
)
from app.services.exceptions import LlmGenerationError


def test_provider_selection_uses_ollama_http_without_loading_model() -> None:
    def fake_post(_url: str, _payload: dict, _timeout: float, _headers: dict | None) -> dict:
        return {"message": {"content": "Ollama response"}}

    provider = create_bielik_provider(
        settings=Settings(llm_provider="ollama-http"),
        ollama_post=fake_post,
    )

    assert isinstance(provider, OllamaHttpBielikProvider)


def test_ollama_provider_posts_chat_payload_and_returns_content() -> None:
    calls: list[tuple[str, dict, float, dict | None]] = []

    def fake_post(url: str, payload: dict, timeout: float, headers: dict | None) -> dict:
        calls.append((url, payload, timeout, headers))
        return {"message": {"content": "Gotowe<|im_end|>"}}

    service = BielikLlmService(
        settings=Settings(
            llm_provider="ollama-http",
            ollama_base_url="http://127.0.0.1:11434/",
            ollama_model="bielik:test",
            ollama_timeout_seconds=7,
            llm_max_new_tokens=64,
            llm_temperature=0.3,
        ),
        ollama_post=fake_post,
    )

    response = service.generate(
        [
            ConversationMessage(role="system", content="System"),
            ConversationMessage(role="user", content="Cześć"),
        ]
    )

    assert response == "Gotowe"
    assert calls[0][0] == "http://127.0.0.1:11434/api/chat"
    assert calls[0][2] == 7
    assert calls[0][3] is None
    assert calls[0][1]["model"] == "bielik:test"
    assert calls[0][1]["stream"] is False
    assert calls[0][1]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Cześć"},
    ]
    assert calls[0][1]["options"] == {"temperature": 0.3, "num_predict": 64}


def test_ollama_provider_adds_google_id_token_header(monkeypatch) -> None:
    calls: list[dict | None] = []

    def fake_post(_url: str, _payload: dict, _timeout: float, headers: dict | None) -> dict:
        calls.append(headers)
        return {"message": {"content": "Gotowe"}}

    monkeypatch.setattr(
        "app.services.bielik.fetch_google_id_token",
        lambda audience: f"token-for-{audience}",
    )
    service = BielikLlmService(
        settings=Settings(
            llm_provider="ollama-http",
            ollama_base_url="https://bielik.example.run.app",
            ollama_auth_mode="google-id-token",
        ),
        ollama_post=fake_post,
    )

    response = service.generate([ConversationMessage(role="user", content="Cześć")])

    assert response == "Gotowe"
    assert calls == [{"Authorization": "Bearer token-for-https://bielik.example.run.app"}]


def test_ollama_provider_rejects_malformed_response() -> None:
    service = BielikLlmService(
        settings=Settings(llm_provider="ollama-http"),
        ollama_post=lambda _url, _payload, _timeout, _headers: {
            "message": {"unexpected": "value"}
        },
    )

    with pytest.raises(LlmGenerationError, match="unexpected response shape"):
        service.generate([ConversationMessage(role="user", content="Hello")])


def test_ollama_provider_wraps_http_transport_errors() -> None:
    def failing_post(_url: str, _payload: dict, _timeout: float, _headers: dict | None) -> dict:
        raise OSError("network down")

    service = BielikLlmService(
        settings=Settings(llm_provider="ollama-http"),
        ollama_post=failing_post,
    )

    with pytest.raises(LlmGenerationError, match="Ollama generation failed"):
        service.generate([ConversationMessage(role="user", content="Hello")])


def test_ollama_provider_preserves_controlled_generation_errors() -> None:
    def failing_post(_url: str, _payload: dict, _timeout: float, _headers: dict | None) -> dict:
        raise LlmGenerationError("Ollama HTTP request timed out.")

    service = BielikLlmService(
        settings=Settings(llm_provider="ollama-http"),
        ollama_post=failing_post,
    )

    with pytest.raises(LlmGenerationError, match="timed out"):
        service.generate([ConversationMessage(role="user", content="Hello")])


def test_google_id_token_reports_missing_dependency(monkeypatch) -> None:
    original_import = __import__

    def blocking_import(name, *args, **kwargs):
        if name.startswith("google.auth") or name.startswith("google.oauth2"):
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocking_import)

    with pytest.raises(LlmGenerationError, match="google-auth"):
        fetch_google_id_token("https://bielik.example.run.app")
