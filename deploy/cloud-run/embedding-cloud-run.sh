#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"
: "${EMBEDDING_SERVICE:=medical-scheduling-embedding}"
: "${EMBEDDING_OLLAMA_MODEL:=embeddinggemma:latest}"
: "${EMBEDDING_MEMORY:=4Gi}"
: "${EMBEDDING_CPU:=4}"
: "${EMBEDDING_CONCURRENCY:=4}"
: "${EMBEDDING_MIN_INSTANCES:=0}"
: "${EMBEDDING_MAX_INSTANCES:=1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "${SCRIPT_DIR}/../ollama-embedding" && pwd)"

gcloud config set project "${PROJECT_ID}"

gcloud run deploy "${EMBEDDING_SERVICE}" \
  --source "${SOURCE_DIR}" \
  --region "${REGION}" \
  --concurrency "${EMBEDDING_CONCURRENCY}" \
  --cpu "${EMBEDDING_CPU}" \
  --memory "${EMBEDDING_MEMORY}" \
  --timeout 600 \
  --port 11434 \
  --min-instances "${EMBEDDING_MIN_INSTANCES}" \
  --max-instances "${EMBEDDING_MAX_INSTANCES}" \
  --no-allow-unauthenticated \
  --set-env-vars "MODEL=${EMBEDDING_OLLAMA_MODEL},OLLAMA_NUM_PARALLEL=${EMBEDDING_CONCURRENCY},OLLAMA_KEEP_ALIVE=-1" \
  --labels "app=medical-scheduling-agent,component=embedding-model"
