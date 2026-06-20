import logging
import json
from typing import Any
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException, status

from app.core.settings import get_settings
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
settings = get_settings()
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
        _run_prewarm_component("ollama_gpu", _assert_ollama_gpu_runtime),
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


def _assert_ollama_gpu_runtime() -> None:
    if settings.runtime_profile != "cloud-run":
        logger.info("Skipping Ollama GPU assertion outside Cloud Run runtime profile.")
        return
    if settings.llm_provider != "ollama-http":
        logger.info("Skipping Ollama GPU assertion for non-Ollama LLM provider.")
        return

    payload = _get_ollama_json("/api/ps")
    models = payload.get("models")
    if not isinstance(models, list) or not models:
        raise RuntimeError("Ollama reports no loaded models after prewarm.")

    loaded_models = [
        model
        for model in models
        if isinstance(model, dict)
        and model.get("model") in {settings.ollama_model, settings.embedding_model_name}
    ]
    if not loaded_models:
        raise RuntimeError("Ollama loaded models do not include Bielik or EmbeddingGemma.")

    cpu_models = [
        str(model.get("model"))
        for model in loaded_models
        if int(model.get("size_vram") or 0) <= 0
    ]
    if cpu_models:
        raise RuntimeError(
            "Ollama did not place loaded model weights in VRAM; CPU models: "
            + ", ".join(cpu_models)
        )

    logger.info(
        "Ollama GPU assertion passed loaded_models=%s",
        [
            {
                "model": model.get("model"),
                "size_vram": model.get("size_vram"),
            }
            for model in loaded_models
        ],
    )


def _get_ollama_json(path: str) -> dict[str, Any]:
    url = f"{settings.ollama_base_url.rstrip('/')}/{path.lstrip('/')}"
    with urlopen(url, timeout=settings.ollama_timeout_seconds) as response:
        raw_body = response.read().decode("utf-8")

    decoded = json.loads(raw_body)
    if not isinstance(decoded, dict):
        raise RuntimeError("Ollama returned an unexpected JSON root for runtime diagnostics.")
    return decoded


def _run_prewarm_component(name: str, operation) -> PrewarmComponentResult:
    try:
        logger.info("Prewarming component=%s", name)
        operation()
        logger.info("Prewarm completed component=%s", name)
        return PrewarmComponentResult(name=name, status="ok")
    except Exception as exc:
        logger.exception("Prewarm failed component=%s", name)
        return PrewarmComponentResult(name=name, status="failed", error_message=str(exc))
