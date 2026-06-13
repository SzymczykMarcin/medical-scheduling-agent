from pathlib import Path

import pytest

from app.core.settings import Settings
from app.models.rag import ConversationMessage
from app.services.bielik import BielikLlmService, format_chatml
from app.services.exceptions import LlmGenerationError


class FakeLlamaModel:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def __call__(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        assert kwargs["max_tokens"] == 128
        assert kwargs["temperature"] == 0.2
        return {"choices": [{"text": "Model response<|im_end|>"}]}


def test_format_chatml_renders_messages() -> None:
    prompt = format_chatml(
        [
            ConversationMessage(role="system", content="System"),
            ConversationMessage(role="user", content="Question"),
        ]
    )

    assert prompt.startswith("<s><|im_start|>system")
    assert "<|im_start|>user\nQuestion<|im_end|>" in prompt
    assert prompt.endswith("<|im_start|>assistant\n")


def test_bielik_service_uses_model_factory_and_strips_stop_marker(tmp_path: Path) -> None:
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"fake")
    fake_model = FakeLlamaModel()
    created_with: list[tuple[Path, Settings]] = []

    def model_factory(path: Path, settings: Settings) -> FakeLlamaModel:
        created_with.append((path, settings))
        return fake_model

    settings = Settings(
        bielik_gguf_path=str(model_path),
        llm_max_new_tokens=128,
        llm_temperature=0.2,
    )
    service = BielikLlmService(settings=settings, model_factory=model_factory)

    response = service.generate([ConversationMessage(role="user", content="Hello")])

    assert response == "Model response"
    assert created_with[0][0] == model_path
    assert fake_model.prompts


def test_bielik_service_fails_when_model_file_is_missing(tmp_path: Path) -> None:
    service = BielikLlmService(
        settings=Settings(bielik_gguf_path=str(tmp_path / "missing.gguf")),
        model_factory=lambda _path, _settings: FakeLlamaModel(),
    )

    with pytest.raises(LlmGenerationError, match="does not exist"):
        service.generate([ConversationMessage(role="user", content="Hello")])
