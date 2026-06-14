from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "deploy"


def test_model_server_deployment_assets_exist() -> None:
    expected_paths = [
        REPO_ROOT / ".dockerignore",
        REPO_ROOT / ".github" / "workflows" / "ci.yml",
        REPO_ROOT / "Dockerfile",
        REPO_ROOT / "frontend" / ".dockerignore",
        REPO_ROOT / "frontend" / "Dockerfile",
        REPO_ROOT / "frontend" / "cloudbuild.yaml",
        REPO_ROOT / "frontend" / "nginx.conf",
        DEPLOY_DIR / "README.md",
        DEPLOY_DIR / "docker-compose.local.yml",
        DEPLOY_DIR / "ollama-bielik" / "Dockerfile",
        DEPLOY_DIR / "ollama-embedding" / "Dockerfile",
        DEPLOY_DIR / "cloud-run" / "deploy-demo.sh",
        DEPLOY_DIR / "cloud-run" / "backend-cloud-run.sh",
        DEPLOY_DIR / "cloud-run" / "frontend-cloud-run.sh",
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


def test_backend_cloud_run_script_deploys_public_demo_backend() -> None:
    content = (DEPLOY_DIR / "cloud-run" / "backend-cloud-run.sh").read_text(encoding="utf-8")

    assert ": \"${PROJECT_ID:?" in content
    assert ": \"${REGION:?" in content
    assert ": \"${FRONTEND_ORIGIN:?" in content
    assert ": \"${OLLAMA_BASE_URL:?" in content
    assert "BACKEND_SERVICE_ACCOUNT_EMAIL" in content
    assert "gcloud artifacts repositories describe" in content
    assert "gcloud artifacts repositories create" in content
    assert "gcloud builds submit" in content
    assert "gcloud run deploy" in content
    assert "--allow-unauthenticated" in content
    assert "RUNTIME_PROFILE=cloud-run" in content
    assert "OLLAMA_AUTH_MODE=${OLLAMA_AUTH_MODE}" in content
    assert "ASR_DEVICE=${ASR_DEVICE}" in content
    assert "RAG_BACKEND=${RAG_BACKEND}" in content
    assert "CALENDAR_STORAGE_BACKEND=${CALENDAR_STORAGE_BACKEND}" in content
    assert "C:/" not in content
    assert "C:\\" not in content


def test_backend_dockerfile_contains_cloud_run_entrypoint() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in content
    assert "COPY backend/app" in content
    assert "COPY data/rag" in content
    assert 'python -m pip install ".[cloud]"' in content
    assert "uvicorn app.main:app" in content


def test_frontend_cloud_run_assets_build_static_react_app() -> None:
    dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (REPO_ROOT / "frontend" / "cloudbuild.yaml").read_text(encoding="utf-8")
    nginx_config = (REPO_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    script = (DEPLOY_DIR / "cloud-run" / "frontend-cloud-run.sh").read_text(encoding="utf-8")

    assert "FROM node:20-alpine AS build" in dockerfile
    assert "ARG VITE_API_BASE_URL" in dockerfile
    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "nginxinc/nginx-unprivileged" in dockerfile
    assert "listen 8080" in nginx_config
    assert "try_files $uri $uri/ /index.html" in nginx_config
    assert "_VITE_API_BASE_URL" in cloudbuild
    assert ": \"${BACKEND_URL:?" in script
    assert "gcloud builds submit" in script
    assert "cloudbuild.yaml" in script
    assert "--allow-unauthenticated" in script
    assert "C:/" not in script
    assert "C:\\" not in script


def test_demo_cloud_run_script_wires_private_model_to_public_backend() -> None:
    content = (DEPLOY_DIR / "cloud-run" / "deploy-demo.sh").read_text(encoding="utf-8")

    assert ": \"${PROJECT_ID:?" in content
    assert ": \"${REGION:?" in content
    assert "PROJECT_ID is still a placeholder" in content
    assert "gcloud projects describe" in content
    assert "gcloud projects list --format='table(projectId,name,projectNumber)'" in content
    assert "gcloud services enable" in content
    assert "gcloud iam service-accounts create" in content
    assert "bielik-cloud-run.sh" in content
    assert "gcloud run services add-iam-policy-binding" in content
    assert "roles/run.invoker" in content
    assert 'OLLAMA_AUTH_MODE="google-id-token"' in content
    assert "backend-cloud-run.sh" in content
    assert "frontend-cloud-run.sh" in content
    assert "gcloud run services update" in content
    assert "CORS_ORIGINS=${FRONTEND_URL}" in content
    assert "/api/rag/ingest" in content
    assert "/api/debug/prewarm" in content
    assert "--basic-only" in content


def test_ci_runs_backend_and_frontend_checks() -> None:
    content = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python -m ruff check ." in content
    assert 'python -m pytest tests -m "not local_ai"' in content
    assert "npm ci" in content
    assert "npm run build" in content
