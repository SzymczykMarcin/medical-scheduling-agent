class ServiceError(Exception):
    """Base class for expected service failures."""


class AudioValidationError(ServiceError):
    """Raised when an uploaded audio payload is invalid."""


class TranscriptionError(ServiceError):
    """Raised when speech-to-text processing fails."""


class RagDataNotReadyError(ServiceError):
    """Raised when the RAG vector store has not been prepared yet."""


class RagAnalysisError(ServiceError):
    """Raised when RAG-based transcript analysis fails."""


class LlmGenerationError(ServiceError):
    """Raised when local LLM generation fails."""
