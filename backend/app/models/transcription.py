from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    """Response returned after local speech transcription."""

    filename: str
    transcript: str
