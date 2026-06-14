import logging
import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

from app.core.settings import Settings, get_settings
from app.services.exceptions import AudioValidationError, TranscriptionError

logger = logging.getLogger(__name__)


class WhisperModelProtocol(Protocol):
    """Protocol for faster-whisper compatible model objects."""

    def transcribe(self, audio: str, **kwargs: Any) -> tuple[Iterable[Any], Any]:
        """Transcribe an audio file path."""


ModelFactory = Callable[[Settings], WhisperModelProtocol]


class TranscriptionService:
    """Transcribe uploaded audio with a local GPU-backed ASR model."""

    def __init__(
        self,
        settings: Settings | None = None,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._model_factory = model_factory or create_faster_whisper_model
        self._model: WhisperModelProtocol | None = None

    def transcribe(self, filename: str, audio: bytes) -> str:
        """Validate an audio payload, transcribe it, and log the transcript."""
        self._validate_audio_payload(filename=filename, audio=audio)

        if self.settings.demo_mode:
            transcript = (
                "Dzień dobry, boli mnie gardło i mam gorączkę od wczoraj. "
                "Najbardziej pasowałaby mi wizyta jutro po południu."
            )
            logger.info("Demo transcription for %s: %s", filename, transcript)
            return transcript

        suffix = _safe_audio_suffix(filename)
        audio_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
                audio_file.write(audio)
                audio_file.flush()
                audio_path = audio_file.name
            transcript = self._transcribe_file(audio_path)
        except TranscriptionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected transcription failure for %s", filename)
            raise TranscriptionError("Nie udało się przepisać przesłanego nagrania.") from exc
        finally:
            if audio_path:
                try:
                    os.unlink(audio_path)
                except OSError:
                    logger.warning("Could not remove temporary audio file: %s", audio_path)

        logger.info("Transcription completed for %s: %s", filename, transcript)
        return transcript

    def prewarm_model(self) -> None:
        """Load the ASR model so the first real recording does not download it."""
        self._get_model()

    def _transcribe_file(self, audio_path: str) -> str:
        model = self._get_model()
        logger.info(
            "Starting ASR transcription with model=%s device=%s compute_type=%s",
            self.settings.asr_model_name,
            self.settings.asr_device,
            self.settings.asr_compute_type,
        )

        try:
            segments, _info = model.transcribe(
                audio_path,
                language="pl",
                beam_size=5,
                vad_filter=True,
            )
            transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        except Exception as exc:
            logger.exception("ASR model failed while transcribing %s", audio_path)
            raise TranscriptionError("Model transkrypcji nie poradził sobie z nagraniem.") from exc

        if not transcript:
            raise TranscriptionError(
                "Transkrypcja jest pusta. Sprawdź mikrofon i nagraj wiadomość ponownie."
            )

        return transcript

    def _get_model(self) -> WhisperModelProtocol:
        if self._model is None:
            logger.info(
                "Loading ASR model=%s on device=%s compute_type=%s",
                self.settings.asr_model_name,
                self.settings.asr_device,
                self.settings.asr_compute_type,
            )
            self._model = self._model_factory(self.settings)
            logger.info("ASR model loaded successfully.")

        return self._model

    def _validate_audio_payload(self, filename: str, audio: bytes) -> None:
        if not audio:
            raise AudioValidationError("Uploaded audio is empty.")

        max_bytes = self.settings.max_audio_upload_mb * 1024 * 1024
        if len(audio) > max_bytes:
            raise AudioValidationError(
                f"Uploaded audio is too large. Limit is {self.settings.max_audio_upload_mb} MB."
            )

        logger.info("Received audio upload filename=%s size_bytes=%s", filename, len(audio))


def create_faster_whisper_model(settings: Settings) -> WhisperModelProtocol:
    """Create the production faster-whisper model instance."""
    if settings.asr_provider != "faster-whisper":
        raise TranscriptionError(f"Nieobsługiwany dostawca ASR: {settings.asr_provider}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError("faster-whisper nie jest zainstalowany.") from exc

    return WhisperModel(
        settings.asr_model_name,
        device=settings.asr_device,
        compute_type=settings.asr_compute_type,
    )


def _safe_audio_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg"}:
        return suffix
    return ".webm"
