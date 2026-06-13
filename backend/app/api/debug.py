import logging

from fastapi import APIRouter

from app.models.debug import AppointmentDebugRequest, AppointmentDebugResponse
from app.services.debug_analysis import AppointmentDebugAnalysisService

router = APIRouter(prefix="/debug", tags=["debug"])
logger = logging.getLogger(__name__)
debug_analysis_service = AppointmentDebugAnalysisService()


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
