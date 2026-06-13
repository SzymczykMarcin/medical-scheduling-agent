import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.calendar import router as calendar_router
from app.api.health import router as health_router
from app.api.rag import router as rag_router
from app.api.voice import router as voice_router
from app.core.logging import configure_logging
from app.core.settings import get_settings


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Medical Scheduling Agent API", version="0.1.0")
    logger = logging.getLogger("app.requests")

    @app.middleware("http")
    async def log_requests(request, call_next):
        start = time.perf_counter()
        origin = request.headers.get("origin")
        logger.info(
            "HTTP request start method=%s path=%s origin=%s",
            request.method,
            request.url.path,
            origin,
        )
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "HTTP request failed method=%s path=%s elapsed_ms=%.1f",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "HTTP request finished method=%s path=%s status=%s elapsed_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(calendar_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")
    app.include_router(voice_router, prefix="/api")
    return app


app = create_app()
