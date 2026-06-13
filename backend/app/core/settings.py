from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    demo_mode: bool = False
    cors_origins_raw: str = Field(
        default=(
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:5397,http://127.0.0.1:5397"
        ),
        alias="CORS_ORIGINS",
    )

    asr_provider: str = "faster-whisper"
    asr_model_name: str = "large-v3-turbo"
    asr_device: str = "cuda"
    asr_compute_type: str = "int8_float16"
    max_audio_upload_mb: int = 50

    llm_provider: Literal["llama-cpp", "ollama-http"] = "llama-cpp"
    bielik_gguf_path: str = (
        "C:/009_Firma/safe_space/interactive-cv/models/bielik-minitron-7b-q4/"
        "minitron-Bielik-7B-v3.0-Instruct-GGUF.Q4_K_M.gguf"
    )
    llm_context_tokens: int = 4096
    llm_gpu_layers: int = -1
    llm_threads: int | None = None
    llm_max_new_tokens: int = 512
    llm_temperature: float = 0.1
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    ollama_timeout_seconds: float = 120.0

    embedding_model_name: str = "sdadas/mmlw-retrieval-roberta-large"
    rag_backend: str = "file"
    chroma_persist_dir: str = str(PROJECT_ROOT / "data" / "chroma")
    chroma_collection_name: str = "medical_scheduling_rules"
    rag_document_dir: str = str(PROJECT_ROOT / "data" / "rag")
    rag_max_context_characters: int = 8000
    retrieval_limit: int = 4
    rag_chunk_characters: int = 1200
    rag_chunk_overlap: int = 180

    sqlite_database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'demo.sqlite3'}"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
