from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "deploy"


def test_model_server_deployment_assets_exist() -> None:
    expected_paths = [
        DEPLOY_DIR / "README.md",
        DEPLOY_DIR / "docker-compose.local.yml",
        DEPLOY_DIR / "ollama-bielik" / "Dockerfile",
        DEPLOY_DIR / "ollama-embedding" / "Dockerfile",
        DEPLOY_DIR / "cloud-run" / "bielik-cloud-run.sh",
        DEPLOY_DIR / "cloud-run" / "embedding-cloud-run.sh",
    ]

    for path in expected_paths:
        assert path.exists(), f"Missing deployment asset: {path}"


def test_ollama_dockerfiles_keep_models_loaded_and_pull_configured_models() -> None:
    for relative_path in [
        "ollama-bielik/Dockerfile",
        "ollama-embedding/Dockerfile",
    ]:
        content = (DEPLOY_DIR / relative_path).read_text(encoding="utf-8")

        assert "FROM ollama/ollama:0.23.4" in content
        assert "ARG MODEL=" in content
        assert "ENV OLLAMA_KEEP_ALIVE=-1" in content
        assert 'ollama pull "${MODEL}"' in content
        assert "COPY entrypoint.sh /entrypoint.sh" in content
        assert 'ENTRYPOINT ["sh", "/entrypoint.sh"]' in content


def test_ollama_entrypoints_pull_runtime_configured_model() -> None:
    for relative_path in [
        "ollama-bielik/entrypoint.sh",
        "ollama-embedding/entrypoint.sh",
    ]:
        content = (DEPLOY_DIR / relative_path).read_text(encoding="utf-8")

        assert "set -eu" in content
        assert "ollama serve &" in content
        assert 'ollama pull "${MODEL}"' in content
        assert 'wait "${server_pid}"' in content


def test_local_compose_exposes_predictable_model_ports() -> None:
    content = (DEPLOY_DIR / "docker-compose.local.yml").read_text(encoding="utf-8")

    assert "bielik-model:" in content
    assert "embedding-model:" in content
    assert "${BIELIK_OLLAMA_PORT:-11434}:11434" in content
    assert "${EMBEDDING_OLLAMA_PORT:-11435}:11434" in content
    assert "OLLAMA_KEEP_ALIVE: \"-1\"" in content


def test_cloud_run_scripts_are_parameterized() -> None:
    for relative_path in [
        "cloud-run/bielik-cloud-run.sh",
        "cloud-run/embedding-cloud-run.sh",
    ]:
        content = (DEPLOY_DIR / relative_path).read_text(encoding="utf-8")

        assert ": \"${PROJECT_ID:?" in content
        assert ": \"${REGION:?" in content
        assert "--source" in content
        assert "--no-allow-unauthenticated" in content
        assert "--labels \"app=medical-scheduling-agent" in content
        assert "C:/" not in content
        assert "C:\\" not in content
