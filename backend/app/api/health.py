from fastapi import APIRouter

from app.core.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "runtime_profile": settings.runtime_profile,
        "llm_provider": settings.llm_provider,
        "rag_backend": settings.rag_backend,
        "asr_provider": settings.asr_provider,
        "calendar_storage_backend": settings.calendar_storage_backend,
        "cloud_storage_mode": settings.cloud_storage_mode,
    }
