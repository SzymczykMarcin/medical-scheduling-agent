from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_local_ollama_profile_parses_without_private_paths() -> None:
    settings = Settings(_env_file=REPO_ROOT / ".env.example.local-ollama")

    assert settings.runtime_profile == "local-ollama"
    assert settings.llm_provider == "ollama-http"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_auth_mode == "none"
    assert settings.rag_backend == "chroma"
    assert settings.calendar_storage_backend == "sqlite"
    assert settings.cloud_storage_mode == "ephemeral"
    assert "C:/" not in settings.bielik_gguf_path
    assert "C:\\" not in settings.bielik_gguf_path


def test_cloud_run_profile_parses_without_private_paths_or_project_ids() -> None:
    profile_path = REPO_ROOT / ".env.example.cloud-run"
    content = profile_path.read_text(encoding="utf-8")
    settings = Settings(_env_file=profile_path)

    assert settings.runtime_profile == "cloud-run"
    assert settings.llm_provider == "ollama-http"
    assert settings.ollama_base_url == "https://your-bielik-service-url"
    assert settings.ollama_auth_mode == "google-id-token"
    assert settings.rag_backend == "chroma"
    assert settings.asr_device == "cpu"
    assert settings.asr_compute_type == "int8"
    assert settings.calendar_storage_backend == "sqlite"
    assert settings.cloud_storage_mode == "ephemeral"
    assert settings.rag_index_mode == "local-chroma"
    assert "C:/" not in content
    assert "C:\\" not in content
    assert "/Users/" not in content
    assert "\\Users\\" not in content


def test_llama_cpp_requires_explicit_model_path() -> None:
    with pytest.raises(ValidationError, match="BIELIK_GGUF_PATH"):
        Settings(llm_provider="llama-cpp", bielik_gguf_path="")


def test_ollama_http_requires_base_url() -> None:
    with pytest.raises(ValidationError, match="OLLAMA_BASE_URL"):
        Settings(llm_provider="ollama-http", ollama_base_url="")


def test_persistent_cloud_storage_requires_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(runtime_profile="cloud-run", cloud_storage_mode="persistent", database_url=None)


def test_sql_calendar_storage_requires_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(calendar_storage_backend="sql", database_url=None)


def test_sql_calendar_storage_accepts_managed_database_url() -> None:
    settings = Settings(
        calendar_storage_backend="sql",
        cloud_storage_mode="persistent",
        database_url="postgresql+psycopg://demo:demo@example.internal/demo",
    )

    assert settings.effective_database_url == "postgresql+psycopg://demo:demo@example.internal/demo"
