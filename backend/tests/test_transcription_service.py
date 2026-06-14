from dataclasses import dataclass

import pytest

from app.core.settings import Settings
from app.services.asr import TranscriptionService
from app.services.exceptions import AudioValidationError


@dataclass
class FakeSegment:
    text: str


class FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def transcribe(self, audio: str, **_kwargs):
        self.calls.append(audio)
        return [FakeSegment(" Dzien dobry "), FakeSegment(" prosze o wizyte. ")], object()


def test_transcribe_rejects_empty_audio() -> None:
    service = TranscriptionService(settings=Settings(demo_mode=False))

    with pytest.raises(AudioValidationError, match="empty"):
        service.transcribe(filename="empty.webm", audio=b"")


def test_transcribe_uses_injected_gpu_model_factory() -> None:
    fake_model = FakeWhisperModel()
    created_with: list[Settings] = []

    def model_factory(settings: Settings) -> FakeWhisperModel:
        created_with.append(settings)
        return fake_model

    settings = Settings(
        demo_mode=False,
        asr_model_name="large-v3-turbo",
        asr_device="cuda",
        asr_compute_type="int8_float16",
    )
    service = TranscriptionService(settings=settings, model_factory=model_factory)

    transcript = service.transcribe(filename="voice.webm", audio=b"fake-audio")

    assert transcript == "Dzien dobry prosze o wizyte."
    assert len(created_with) == 1
    assert created_with[0].asr_device == "cuda"
    assert fake_model.calls


def test_transcribe_loads_model_once() -> None:
    fake_model = FakeWhisperModel()
    factory_calls = 0

    def model_factory(_settings: Settings) -> FakeWhisperModel:
        nonlocal factory_calls
        factory_calls += 1
        return fake_model

    service = TranscriptionService(
        settings=Settings(demo_mode=False),
        model_factory=model_factory,
    )

    service.transcribe(filename="first.webm", audio=b"first")
    service.transcribe(filename="second.webm", audio=b"second")

    assert factory_calls == 1


def test_prewarm_model_runs_runtime_decode() -> None:
    fake_model = FakeWhisperModel()
    factory_calls = 0

    def model_factory(_settings: Settings) -> FakeWhisperModel:
        nonlocal factory_calls
        factory_calls += 1
        return fake_model

    service = TranscriptionService(
        settings=Settings(demo_mode=False),
        model_factory=model_factory,
    )

    service.prewarm_model()

    assert factory_calls == 1
    assert len(fake_model.calls) == 1
    assert fake_model.calls[0].endswith(".wav")
