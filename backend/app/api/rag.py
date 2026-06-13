import logging

from fastapi import APIRouter, HTTPException, status

from app.models.ingestion import RagIngestionResponse
from app.services.exceptions import RagDataNotReadyError, ServiceError
from app.services.rag_ingestion import RagIngestionService

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger(__name__)
ingestion_service = RagIngestionService()


@router.post("/ingest", response_model=RagIngestionResponse)
def ingest_rag_documents() -> RagIngestionResponse:
    """Rebuild the local RAG index from configured documents."""
    try:
        return ingestion_service.rebuild_index()
    except RagDataNotReadyError as exc:
        logger.warning("RAG ingestion rejected: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ServiceError as exc:
        logger.exception("RAG ingestion failed.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
