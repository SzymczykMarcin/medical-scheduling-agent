#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"
: "${FRONTEND_ORIGIN:?Set FRONTEND_ORIGIN to the public frontend URL.}"
: "${OLLAMA_BASE_URL:?Set OLLAMA_BASE_URL to the deployed Bielik service URL.}"

: "${BACKEND_SERVICE:=medical-scheduling-backend}"
: "${AR_REPOSITORY:=medical-scheduling-agent}"
: "${BACKEND_IMAGE:=${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${BACKEND_SERVICE}:latest}"
: "${BACKEND_MEMORY:=4Gi}"
: "${BACKEND_CPU:=2}"
: "${BACKEND_CONCURRENCY:=8}"
: "${BACKEND_MAX_INSTANCES:=2}"
: "${ASR_MODEL_NAME:=large-v3-turbo}"
: "${ASR_DEVICE:=cpu}"
: "${ASR_COMPUTE_TYPE:=int8}"
: "${OLLAMA_MODEL:=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0}"

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

gcloud run deploy "${BACKEND_SERVICE}" \
  --image "${BACKEND_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --concurrency "${BACKEND_CONCURRENCY}" \
  --cpu "${BACKEND_CPU}" \
  --memory "${BACKEND_MEMORY}" \
  --timeout 600 \
  --max-instances "${BACKEND_MAX_INSTANCES}" \
  --set-env-vars "RUNTIME_PROFILE=cloud-run,BACKEND_HOST=0.0.0.0,BACKEND_PORT=8080,CORS_ORIGINS=${FRONTEND_ORIGIN},DEMO_MODE=false,ASR_PROVIDER=faster-whisper,ASR_MODEL_NAME=${ASR_MODEL_NAME},ASR_DEVICE=${ASR_DEVICE},ASR_COMPUTE_TYPE=${ASR_COMPUTE_TYPE},LLM_PROVIDER=ollama-http,OLLAMA_BASE_URL=${OLLAMA_BASE_URL},OLLAMA_MODEL=${OLLAMA_MODEL},RAG_BACKEND=chroma,CHROMA_PERSIST_DIR=/tmp/medical-scheduling-agent/chroma,RAG_DOCUMENT_DIR=/app/data/rag,SQLITE_DATABASE_URL=sqlite:////tmp/medical-scheduling-agent/demo.sqlite3" \
  --labels "app=medical-scheduling-agent,component=backend"
