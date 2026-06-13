import logging

from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status

from app.models.appointment import AppointmentResponse
from app.models.transcription import TranscriptionResponse
from app.services.appointment_pipeline import AppointmentPipeline
from app.services.asr import TranscriptionService
from app.services.exceptions import AudioValidationError, ServiceError, TranscriptionError

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)
pipeline = AppointmentPipeline()
transcription_service = TranscriptionService()


@router.post("/transcriptions", response_model=TranscriptionResponse)
async def transcribe_voice_message(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """Transcribe an uploaded voice message and log the recognized text."""
    audio_bytes = await audio.read()
    filename = audio.filename or "recording.webm"

    try:
        transcript = transcription_service.transcribe(filename=filename, audio=audio_bytes)
    except AudioValidationError as exc:
        logger.warning("Rejected audio upload filename=%s reason=%s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except TranscriptionError as exc:
        logger.warning("Could not transcribe audio filename=%s reason=%s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ServiceError as exc:
        logger.exception("Voice transcription failed filename=%s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected voice transcription failure filename=%s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected transcription failure. Check backend logs.",
        ) from exc

    return TranscriptionResponse(filename=filename, transcript=transcript)


@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment_from_voice(
    audio: UploadFile = File(...),
    origin: str | None = Header(default=None),
    user_agent: str | None = Header(default=None),
) -> AppointmentResponse:
    audio_bytes = await audio.read()
    filename = audio.filename or "recording.webm"

    logger.info(
        "Received appointment audio upload filename=%s content_type=%s size_bytes=%s origin=%s "
        "user_agent=%s",
        filename,
        audio.content_type,
        len(audio_bytes),
        origin,
        user_agent,
    )

    try:
        response = pipeline.handle_audio_message(filename=filename, audio=audio_bytes)
        logger.info(
            "Appointment pipeline finished status=%s transcript_chars=%s event_created=%s",
            response.status,
            len(response.transcript),
            response.event is not None,
        )
        return response
    except AudioValidationError as exc:
        logger.warning("Rejected appointment audio upload filename=%s reason=%s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except TranscriptionError as exc:
        logger.warning("Could not transcribe appointment audio filename=%s reason=%s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ServiceError as exc:
        logger.exception("Appointment voice pipeline failed filename=%s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected appointment pipeline failure filename=%s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected appointment pipeline failure. Check backend logs.",
        ) from exc
