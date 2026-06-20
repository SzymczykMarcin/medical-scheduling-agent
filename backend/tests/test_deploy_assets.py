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
        assert "--min-instances" in content
        assert "--labels \"app=medical-scheduling-agent" in content
        assert "C:/" not in content
        assert "C:\\" not in content


def test_cloud_run_demo_defaults_match_l4_gpu_constraints() -> None:
    bielik = (DEPLOY_DIR / "cloud-run" / "bielik-cloud-run.sh").read_text(encoding="utf-8")
    backend = (DEPLOY_DIR / "cloud-run" / "backend-cloud-run.sh").read_text(encoding="utf-8")
    embedding = (DEPLOY_DIR / "cloud-run" / "embedding-cloud-run.sh").read_text(encoding="utf-8")
    frontend = (DEPLOY_DIR / "cloud-run" / "frontend-cloud-run.sh").read_text(encoding="utf-8")

    assert ': "${BIELIK_MEMORY:=16Gi}"' in bielik
    assert ': "${BACKEND_MEMORY:=16Gi}"' in backend
    assert ': "${EMBEDDING_MEMORY:=4Gi}"' in embedding
    assert ': "${FRONTEND_MEMORY:=128Mi}"' in frontend
    assert ': "${FRONTEND_MAX_INSTANCES:=1}"' in frontend


def test_ollama_cloud_run_services_use_ollama_port() -> None:
    for relative_path in [
        "cloud-run/bielik-cloud-run.sh",
        "cloud-run/embedding-cloud-run.sh",
    ]:
        content = (DEPLOY_DIR / relative_path).read_text(encoding="utf-8")

        assert "--port 11434" in content


def test_backend_cloud_run_script_deploys_public_demo_backend() -> None:
    content = (DEPLOY_DIR / "cloud-run" / "backend-cloud-run.sh").read_text(encoding="utf-8")

    assert ": \"${PROJECT_ID:?" in content
    assert ": \"${REGION:?" in content
    assert ": \"${FRONTEND_ORIGIN:?" in content
    assert ': "${OLLAMA_BASE_URL:=http://127.0.0.1:11434}"' in content
    assert "BACKEND_SERVICE_ACCOUNT_EMAIL" in content
    assert ": \"${BACKEND_MEMORY:=16Gi}\"" in content
    assert ": \"${BACKEND_CPU:=4}\"" in content
    assert ": \"${BACKEND_CONCURRENCY:=1}\"" in content
    assert ": \"${BACKEND_MIN_INSTANCES:=0}\"" in content
    assert ": \"${BACKEND_MAX_INSTANCES:=1}\"" in content
    assert ": \"${BACKEND_GPU_ENABLED:=true}\"" in content
    assert ": \"${BACKEND_GPU_TYPE:=nvidia-l4}\"" in content
    assert ": \"${ASR_DEVICE:=cuda}\"" in content
    assert ": \"${ASR_COMPUTE_TYPE:=int8_float16}\"" in content
    assert ": \"${OLLAMA_KEEP_ALIVE:=-1}\"" in content
    assert ": \"${OLLAMA_NUM_PARALLEL:=1}\"" in content
    assert ": \"${OLLAMA_DEBUG:=1}\"" in content
    assert ": \"${OLLAMA_TIMEOUT_SECONDS:=600}\"" in content
    assert ": \"${PULL_MODELS_ON_START:=0}\"" in content
    assert ": \"${RAG_BACKEND:=bigquery-vector}\"" in content
    assert ": \"${RAG_INDEX_MODE:=managed-vector}\"" in content
    assert ": \"${EMBEDDING_PROVIDER:=ollama-http}\"" in content
    assert ': "${EMBEDDING_BASE_URL:=http://127.0.0.1:11434}"' in content
    assert ": \"${EMBEDDING_MODEL_NAME:=embeddinggemma:latest}\"" in content
    assert ": \"${EMBEDDING_AUTH_MODE:=none}\"" in content
    assert ": \"${EMBEDDING_TIMEOUT_SECONDS:=600}\"" in content
    assert ": \"${EMBEDDING_DEVICE:=cpu}\"" in content
    assert "gcloud artifacts repositories describe" in content
    assert "gcloud artifacts repositories create" in content
    assert "gcloud builds submit" in content
    assert "gcloud run deploy" in content
    assert "--allow-unauthenticated" in content
    assert "--gpu 1" in content
    assert '--gpu-type "${BACKEND_GPU_TYPE}"' in content
    assert "--no-cpu-throttling" in content
    assert "--no-gpu-zonal-redundancy" in content
    assert "--remove-env-vars" not in content
    assert '--min-instances "${BACKEND_MIN_INSTANCES}"' in content
    assert "RUNTIME_PROFILE=cloud-run" in content
    assert "OLLAMA_AUTH_MODE=${OLLAMA_AUTH_MODE}" in content
    assert "OLLAMA_LLM_LIBRARY=${OLLAMA_LLM_LIBRARY}" not in content
    assert "OLLAMA_KEEP_ALIVE=${OLLAMA_KEEP_ALIVE}" in content
    assert "OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL}" in content
    assert "OLLAMA_DEBUG=${OLLAMA_DEBUG}" in content
    assert "OLLAMA_TIMEOUT_SECONDS=${OLLAMA_TIMEOUT_SECONDS}" in content
    assert "PULL_MODELS_ON_START=${PULL_MODELS_ON_START}" in content
    assert "ASR_DEVICE=${ASR_DEVICE}" in content
    assert "EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER}" in content
    assert "EMBEDDING_BASE_URL=${EMBEDDING_BASE_URL}" in content
    assert "EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME}" in content
    assert "EMBEDDING_AUTH_MODE=${EMBEDDING_AUTH_MODE}" in content
    assert "EMBEDDING_TIMEOUT_SECONDS=${EMBEDDING_TIMEOUT_SECONDS}" in content
    assert "EMBEDDING_DEVICE=${EMBEDDING_DEVICE}" in content
    assert "RAG_BACKEND=${RAG_BACKEND}" in content
    assert "CALENDAR_STORAGE_BACKEND=${CALENDAR_STORAGE_BACKEND}" in content
    assert "C:/" not in content
    assert "C:\\" not in content


def test_backend_dockerfile_contains_cloud_run_entrypoint() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM ollama/ollama:0.23.4" in content
    assert "FROM python:3.12-slim" not in content
    assert "COPY --from=ollama-runtime" not in content
    assert "ENV VIRTUAL_ENV=/opt/venv" in content
    assert 'ENV PATH="/opt/venv/bin:${PATH}"' in content
    assert "ENV OLLAMA_LIBRARY_PATH=/usr/lib/ollama" in content
    assert "ENV OLLAMA_HOST=127.0.0.1:11434" in content
    assert "ENV OLLAMA_MODELS=/models" in content
    assert "ENV OLLAMA_KEEP_ALIVE=-1" in content
    assert "ARG BIELIK_OLLAMA_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0" in content
    assert "ARG EMBEDDING_OLLAMA_MODEL=embeddinggemma:latest" in content
    assert "Unsupported ollama base image" in content
    assert "apt-get install -y --no-install-recommends" in content
    assert "python3" in content
    assert "python3-pip" in content
    assert "python3-venv" in content
    assert 'python3 -m venv "${VIRTUAL_ENV}"' in content
    assert "COPY backend/app" in content
    assert "COPY data/rag" in content
    assert 'python -m pip install ".[cloud]"' in content
    assert 'ollama pull "${BIELIK_OLLAMA_MODEL}"' in content
    assert 'ollama pull "${EMBEDDING_OLLAMA_MODEL}"' in content
    assert "COPY deploy/cloud-run/backend-entrypoint.sh /app/backend-entrypoint.sh" in content
    assert "useradd --create-home" in content
    assert 'chown -R app:app /app /tmp/medical-scheduling-agent "${OLLAMA_MODELS}"' in content
    assert "USER app" in content
    assert "ENTRYPOINT []" in content
    assert 'CMD ["sh", "/app/backend-entrypoint.sh"]' in content


def test_backend_entrypoint_starts_local_ollama_before_api() -> None:
    content = (DEPLOY_DIR / "cloud-run" / "backend-entrypoint.sh").read_text(encoding="utf-8")

    assert "set -eu" in content
    assert 'export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"' in content
    assert "PYTHON_SITE_PACKAGES" in content
    assert 'export NVIDIA_SITE_PACKAGES="${NVIDIA_SITE_PACKAGES:-${PYTHON_SITE_PACKAGES}/nvidia}"' in content
    assert "PYTHON_CUDA_LIBRARY_PATH" in content
    assert "log_startup_diagnostics" in content
    assert "OLLAMA_KEEP_ALIVE" in content
    assert "OLLAMA_NUM_PARALLEL" in content
    assert "OLLAMA_DEBUG" in content
    assert "OLLAMA_LLM_LIBRARY=${OLLAMA_LLM_LIBRARY:-<unset/autodetect>}" in content
    assert "OLLAMA_LIBRARY_PATH" in content
    assert "LD_LIBRARY_PATH" in content
    assert "CUDA_VISIBLE_DEVICES" in content
    assert "NVIDIA_VISIBLE_DEVICES" in content
    assert "nvidia-smi" in content
    assert "libcublas.so" in content
    assert "libcudart.so" in content
    assert "libcudnn.so" in content
    assert "env \\" in content
    assert "-u OLLAMA_LLM_LIBRARY" in content
    assert "ollama serve &" in content
    assert 'export LD_LIBRARY_PATH="${PYTHON_CUDA_LIBRARY_PATH}:${ORIGINAL_LD_LIBRARY_PATH}"' in content
    assert 'kill -0 "${ollama_pid}"' in content
    assert "Ollama server failed to start." in content
    assert 'ollama pull "${OLLAMA_MODEL:-SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0}"' in content
    assert 'ollama pull "${EMBEDDING_MODEL_NAME:-embeddinggemma:latest}"' in content
    assert "uvicorn app.main:app" in content


def test_backend_cloud_extra_installs_cuda_12_runtime_libraries() -> None:
    content = (REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")

    assert "local-rag = [" in content
    assert '"chromadb>=0.5.0"' in content
    assert '"sentence-transformers>=3.0.0"' in content
    assert "postgres = [" in content
    assert '"psycopg[binary]>=3.2.0"' in content
    assert "legacy-private-model-services = [" in content
    assert '"google-auth>=2.35.0"' in content
    assert "nvidia-cublas-cu12==12.6.4.1" in content
    assert "nvidia-cuda-runtime-cu12==12.6.77" in content
    assert "nvidia-cudnn-cu12==9.5.1.17" in content
    assert content.index("local-rag = [") < content.index('"chromadb>=0.5.0"')
    assert content.index("cloud = [") < content.index("nvidia-cublas-cu12")
    assert content.index("postgres = [") < content.index('"psycopg[binary]>=3.2.0"')
    assert content.index("legacy-private-model-services = [") < content.index('"google-auth>=2.35.0"')
    assert content.index("cloud = [") < content.index("postgres = [")
    cloud_extra = content[content.index("cloud = [") : content.index("postgres = [")]
    assert "chromadb" not in cloud_extra
    assert "sentence-transformers" not in cloud_extra
    assert "psycopg" not in cloud_extra
    assert "google-auth" not in cloud_extra


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


def test_demo_cloud_run_script_wires_all_ai_into_single_gpu_backend() -> None:
    content = (DEPLOY_DIR / "cloud-run" / "deploy-demo.sh").read_text(encoding="utf-8")

    assert ": \"${PROJECT_ID:?" in content
    assert ": \"${REGION:?" in content
    assert "PROJECT_ID is still a placeholder" in content
    assert "gcloud projects describe" in content
    assert "gcloud projects list --format='table(projectId,name,projectNumber)'" in content
    assert "gcloud services enable" in content
    assert ": \"${REPLACE_EXISTING_SERVICES:=0}\"" in content
    assert "Replacing existing Cloud Run demo services before deploy." in content
    assert "gcloud run services delete" in content
    assert '"medical-scheduling-bielik"' in content
    assert '"medical-scheduling-embedding"' in content
    assert "gcloud iam service-accounts create" in content
    assert "bielik-cloud-run.sh" not in content
    assert "embedding-cloud-run.sh" not in content
    assert "gcloud run services add-iam-policy-binding" not in content
    assert "roles/run.invoker" not in content
    assert 'OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"' in content
    assert 'OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}"' in content
    assert 'OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"' in content
    assert 'OLLAMA_DEBUG="${OLLAMA_DEBUG:-1}"' in content
    assert 'OLLAMA_AUTH_MODE="${OLLAMA_AUTH_MODE:-none}"' in content
    assert 'OLLAMA_TIMEOUT_SECONDS="${OLLAMA_TIMEOUT_SECONDS:-600}"' in content
    assert 'EMBEDDING_BASE_URL="${EMBEDDING_BASE_URL:-http://127.0.0.1:11434}"' in content
    assert 'EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-ollama-http}"' in content
    assert 'EMBEDDING_AUTH_MODE="${EMBEDDING_AUTH_MODE:-none}"' in content
    assert 'EMBEDDING_TIMEOUT_SECONDS="${EMBEDDING_TIMEOUT_SECONDS:-600}"' in content
    assert 'RAG_BACKEND="${RAG_BACKEND:-bigquery-vector}"' in content
    assert 'RAG_INDEX_MODE="${RAG_INDEX_MODE:-managed-vector}"' in content
    assert 'BIGQUERY_PROJECT_ID="${BIGQUERY_PROJECT_ID:-${PROJECT_ID}}"' in content
    assert 'BACKEND_GPU_ENABLED="${BACKEND_GPU_ENABLED:-true}"' in content
    assert 'BACKEND_GPU_TYPE="${BACKEND_GPU_TYPE:-nvidia-l4}"' in content
    assert 'BACKEND_MEMORY="${BACKEND_MEMORY:-16Gi}"' in content
    assert 'BACKEND_MIN_INSTANCES="${BACKEND_MIN_INSTANCES:-0}"' in content
    assert 'BACKEND_MAX_INSTANCES="${BACKEND_MAX_INSTANCES:-1}"' in content
    assert 'ASR_DEVICE="${ASR_DEVICE:-cuda}"' in content
    assert 'ASR_COMPUTE_TYPE="${ASR_COMPUTE_TYPE:-int8_float16}"' in content
    assert "backend-cloud-run.sh" in content
    assert "frontend-cloud-run.sh" in content
    assert "gcloud run services update" in content
    assert "CORS_ORIGINS=${FRONTEND_URL}" in content
    assert "/api/rag/ingest" in content
    assert "/api/debug/prewarm" in content
    assert "--basic-only" in content
    assert "Preparing backend before exposing the frontend." in content
    assert "print_backend_logs_on_error" in content
    assert "Recent backend logs for diagnostics:" in content
    assert "gcloud run services logs read" in content
    assert "Backend preparation completed. Deploying frontend." in content
    assert "Demo deployment completed successfully." in content
    assert "Model runtime: local Ollama inside backend" in content
    assert content.index("/api/rag/ingest") < content.index("frontend-cloud-run.sh")
    assert content.index("/api/debug/prewarm") < content.index("frontend-cloud-run.sh")
    assert content.index("--basic-only") < content.index("frontend-cloud-run.sh")
    assert content.index("Frontend URL:") > content.index("Backend preparation completed.")


def test_ci_runs_backend_and_frontend_checks() -> None:
    content = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'python -m pip install -e ".[dev,local-rag]"' in content
    assert "python -m ruff check ." in content
    assert 'python -m pytest tests -m "not local_ai"' in content
    assert "npm ci" in content
    assert "npm run build" in content
