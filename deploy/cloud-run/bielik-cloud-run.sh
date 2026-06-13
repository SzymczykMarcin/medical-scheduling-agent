#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"
: "${BIELIK_SERVICE:=medical-scheduling-bielik}"
: "${BIELIK_OLLAMA_MODEL:=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0}"
: "${BIELIK_MEMORY:=16Gi}"
: "${BIELIK_CPU:=8}"
: "${BIELIK_CONCURRENCY:=4}"
: "${BIELIK_MAX_INSTANCES:=1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "${SCRIPT_DIR}/../ollama-bielik" && pwd)"

gcloud config set project "${PROJECT_ID}"

gcloud run deploy "${BIELIK_SERVICE}" \
  --source "${SOURCE_DIR}" \
  --region "${REGION}" \
  --concurrency "${BIELIK_CONCURRENCY}" \
  --cpu "${BIELIK_CPU}" \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --memory "${BIELIK_MEMORY}" \
  --timeout 600 \
  --max-instances "${BIELIK_MAX_INSTANCES}" \
  --no-allow-unauthenticated \
  --no-cpu-throttling \
  --no-gpu-zonal-redundancy \
  --set-env-vars "MODEL=${BIELIK_OLLAMA_MODEL},OLLAMA_NUM_PARALLEL=${BIELIK_CONCURRENCY},OLLAMA_KEEP_ALIVE=-1" \
  --labels "app=medical-scheduling-agent,component=bielik-model"

