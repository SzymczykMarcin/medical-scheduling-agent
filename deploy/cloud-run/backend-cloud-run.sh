#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"
: "${FRONTEND_ORIGIN:?Set FRONTEND_ORIGIN to the public frontend URL.}"
: "${OLLAMA_BASE_URL:?Set OLLAMA_BASE_URL to the deployed Bielik service URL.}"

: "${BACKEND_SERVICE:=medical-scheduling-backend}"
: "${BACKEND_SERVICE_ACCOUNT_EMAIL:=}"
: "${AR_REPOSITORY:=medical-scheduling-agent}"
: "${BACKEND_IMAGE:=${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${BACKEND_SERVICE}:latest}"
: "${BACKEND_MEMORY:=16Gi}"
: "${BACKEND_CPU:=4}"
: "${BACKEND_CONCURRENCY:=1}"
: "${BACKEND_MIN_INSTANCES:=0}"
: "${BACKEND_MAX_INSTANCES:=1}"
: "${BACKEND_GPU_ENABLED:=true}"
: "${BACKEND_GPU_TYPE:=nvidia-l4}"
: "${ASR_MODEL_NAME:=large-v3-turbo}"
: "${ASR_DEVICE:=cuda}"
: "${ASR_COMPUTE_TYPE:=int8_float16}"
: "${OLLAMA_MODEL:=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0}"
: "${OLLAMA_AUTH_MODE:=google-id-token}"
: "${OLLAMA_TIMEOUT_SECONDS:=600}"
: "${CALENDAR_STORAGE_BACKEND:=sqlite}"
: "${CLOUD_STORAGE_MODE:=ephemeral}"
: "${DATABASE_URL:=}"
: "${RAG_BACKEND:=bigquery-vector}"
: "${RAG_INDEX_MODE:=managed-vector}"
: "${EMBEDDING_PROVIDER:=ollama-http}"
: "${EMBEDDING_BASE_URL:=}"
: "${EMBEDDING_MODEL_NAME:=embeddinggemma:latest}"
: "${EMBEDDING_AUTH_MODE:=google-id-token}"
: "${EMBEDDING_TIMEOUT_SECONDS:=600}"
: "${EMBEDDING_DEVICE:=cpu}"
: "${BIGQUERY_PROJECT_ID:=${PROJECT_ID}}"

if [ "${RAG_BACKEND}" = "bigquery-vector" ] && [ -z "${EMBEDDING_BASE_URL}" ]; then
  echo "EMBEDDING_BASE_URL is required when RAG_BACKEND=bigquery-vector." >&2
  echo "Deploy the embedding Cloud Run service first and pass its service URL." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

gcloud config set project "${PROJECT_ID}"

gcloud artifacts repositories describe "${AR_REPOSITORY}" \
  --location "${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${AR_REPOSITORY}" \
    --repository-format docker \
    --location "${REGION}" \
    --description "Medical Scheduling Agent demo images"

gcloud builds submit "${REPO_ROOT}" \
  --tag "${BACKEND_IMAGE}"

service_account_args=()
if [ -n "${BACKEND_SERVICE_ACCOUNT_EMAIL}" ]; then
  service_account_args=(--service-account "${BACKEND_SERVICE_ACCOUNT_EMAIL}")
fi

gpu_args=()
if [ "${BACKEND_GPU_ENABLED}" = "true" ]; then
  gpu_args=(
    --gpu 1
    --gpu-type "${BACKEND_GPU_TYPE}"
    --no-cpu-throttling
    --no-gpu-zonal-redundancy
  )
fi

gcloud run deploy "${BACKEND_SERVICE}" \
  --image "${BACKEND_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  "${service_account_args[@]}" \
  "${gpu_args[@]}" \
  --concurrency "${BACKEND_CONCURRENCY}" \
  --cpu "${BACKEND_CPU}" \
  --memory "${BACKEND_MEMORY}" \
  --timeout 600 \
  --min-instances "${BACKEND_MIN_INSTANCES}" \
  --max-instances "${BACKEND_MAX_INSTANCES}" \
  --set-env-vars "RUNTIME_PROFILE=cloud-run,BACKEND_HOST=0.0.0.0,BACKEND_PORT=8080,CORS_ORIGINS=${FRONTEND_ORIGIN},DEMO_MODE=false,ASR_PROVIDER=faster-whisper,ASR_MODEL_NAME=${ASR_MODEL_NAME},ASR_DEVICE=${ASR_DEVICE},ASR_COMPUTE_TYPE=${ASR_COMPUTE_TYPE},LLM_PROVIDER=ollama-http,OLLAMA_BASE_URL=${OLLAMA_BASE_URL},OLLAMA_MODEL=${OLLAMA_MODEL},OLLAMA_AUTH_MODE=${OLLAMA_AUTH_MODE},OLLAMA_TIMEOUT_SECONDS=${OLLAMA_TIMEOUT_SECONDS},RAG_BACKEND=${RAG_BACKEND},RAG_INDEX_MODE=${RAG_INDEX_MODE},EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER},EMBEDDING_BASE_URL=${EMBEDDING_BASE_URL},EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME},EMBEDDING_AUTH_MODE=${EMBEDDING_AUTH_MODE},EMBEDDING_TIMEOUT_SECONDS=${EMBEDDING_TIMEOUT_SECONDS},EMBEDDING_DEVICE=${EMBEDDING_DEVICE},BIGQUERY_PROJECT_ID=${BIGQUERY_PROJECT_ID},BIGQUERY_DATASET_ID=${BIGQUERY_DATASET_ID:-rag_dataset},BIGQUERY_TABLE_ID=${BIGQUERY_TABLE_ID:-medical_scheduling_rules},RAG_DOCUMENT_DIR=/app/data/rag,CALENDAR_STORAGE_BACKEND=${CALENDAR_STORAGE_BACKEND},SEED_DEMO_CALENDAR=true,CLOUD_STORAGE_MODE=${CLOUD_STORAGE_MODE},DATABASE_URL=${DATABASE_URL},SQLITE_DATABASE_URL=sqlite:////tmp/medical-scheduling-agent/demo.sqlite3" \
  --labels "app=medical-scheduling-agent,component=backend"
