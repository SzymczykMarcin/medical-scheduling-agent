import logging

from fastapi import APIRouter, HTTPException, status

from app.models.debug import (
    AppointmentDebugRequest,
    AppointmentDebugResponse,
    PrewarmComponentResult,
    PrewarmResponse,
)
from app.models.rag import ConversationMessage
from app.services.debug_analysis import AppointmentDebugAnalysisService
from app.services.asr import TranscriptionService
from app.services.bielik import BielikLlmService
from app.services.embeddings import EmbeddingService

router = APIRouter(prefix="/debug", tags=["debug"])
logger = logging.getLogger(__name__)
debug_analysis_service = AppointmentDebugAnalysisService()
transcription_service = TranscriptionService()
llm_service = BielikLlmService()
embedding_service = EmbeddingService()


@router.post("/appointment-analysis", response_model=AppointmentDebugResponse)
def debug_appointment_analysis(request: AppointmentDebugRequest) -> AppointmentDebugResponse:
    """Return a developer diagnostic view of the text appointment flow."""
    logger.info(
        "Received appointment debug request transcript_chars=%s today=%s",
        len(request.transcript),
        request.today.isoformat() if request.today else None,
    )
    return debug_analysis_service.analyze(
        transcript=request.transcript,
        today=request.today,
    )


@router.post("/prewarm", response_model=PrewarmResponse)
def prewarm_demo_models() -> PrewarmResponse:
    """Load demo AI components before the first manual browser test."""
    components = [
        _run_prewarm_component("asr", transcription_service.prewarm_model),
        _run_prewarm_component("embedding", _prewarm_embedding),
        _run_prewarm_component("bielik", _prewarm_bielik),
    ]
    response = PrewarmResponse(
        status="ok" if all(component.status == "ok" for component in components) else "failed",
        components=components,
    )
    if response.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(),
        )
    return response


def _prewarm_bielik() -> None:
    llm_service.generate(
        [
            ConversationMessage(
                role="user",
                content="Odpowiedz jednym krótkim zdaniem po polsku: gotowe.",
            )
        ]
    )


def _prewarm_embedding() -> None:
    embedding_service.embed_query("Test gotowosci indeksu RAG.")


def _run_prewarm_component(name: str, operation) -> PrewarmComponentResult:
    try:
        logger.info("Prewarming component=%s", name)
        operation()
        logger.info("Prewarm completed component=%s", name)
        return PrewarmComponentResult(name=name, status="ok")
    except Exception as exc:
        logger.exception("Prewarm failed component=%s", name)
        return PrewarmComponentResult(name=name, status="failed", error_message=str(exc))
