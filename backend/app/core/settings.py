from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    demo_mode: bool = False
    runtime_profile: Literal["local-ollama", "cloud-run", "custom"] = "local-ollama"
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

    llm_provider: Literal["llama-cpp", "ollama-http"] = "ollama-http"
    bielik_gguf_path: str = ""
    llm_context_tokens: int = 4096
    llm_gpu_layers: int = -1
    llm_threads: int | None = None
    llm_max_new_tokens: int = 512
    llm_temperature: float = 0.1
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    ollama_timeout_seconds: float = 120.0

    embedding_model_name: str = "sdadas/mmlw-retrieval-roberta-large"
    rag_backend: Literal["chroma", "bigquery-vector"] = "chroma"
    chroma_persist_dir: str = str(PROJECT_ROOT / "data" / "chroma")
    chroma_collection_name: str = "medical_scheduling_rules"
    bigquery_project_id: str | None = None
    bigquery_dataset_id: str = "rag_dataset"
    bigquery_table_id: str = "medical_scheduling_rules"
    rag_document_dir: str = str(PROJECT_ROOT / "data" / "rag")
    rag_max_context_characters: int = 8000
    retrieval_limit: int = 4
    rag_chunk_characters: int = 1200
    rag_chunk_overlap: int = 180

    sqlite_database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'demo.sqlite3'}"

    @model_validator(mode="after")
    def validate_provider_configuration(self) -> "Settings":
        """Validate selected provider configuration without exposing secrets."""
        if self.llm_provider == "llama-cpp" and not self.bielik_gguf_path.strip():
            raise ValueError("BIELIK_GGUF_PATH is required when LLM_PROVIDER=llama-cpp.")
        if self.llm_provider == "ollama-http" and not self.ollama_base_url.strip():
            raise ValueError("OLLAMA_BASE_URL is required when LLM_PROVIDER=ollama-http.")
        if self.rag_backend == "bigquery-vector" and not self.bigquery_project_id:
            raise ValueError("BIGQUERY_PROJECT_ID is required when RAG_BACKEND=bigquery-vector.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
