#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"
: "${BACKEND_URL:?Set BACKEND_URL to the deployed backend service URL.}"

: "${FRONTEND_SERVICE:=medical-scheduling-frontend}"
: "${AR_REPOSITORY:=medical-scheduling-agent}"
: "${FRONTEND_IMAGE:=${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${FRONTEND_SERVICE}:latest}"
: "${FRONTEND_MEMORY:=512Mi}"
: "${FRONTEND_CPU:=1}"
: "${FRONTEND_CONCURRENCY:=80}"
: "${FRONTEND_MAX_INSTANCES:=2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/frontend"

gcloud config set project "${PROJECT_ID}"

gcloud artifacts repositories describe "${AR_REPOSITORY}" \
  --location "${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${AR_REPOSITORY}" \
    --repository-format docker \
    --location "${REGION}" \
    --description "Medical Scheduling Agent demo images"

gcloud builds submit "${SOURCE_DIR}" \
  --config "${SOURCE_DIR}/cloudbuild.yaml" \
  --substitutions "_IMAGE=${FRONTEND_IMAGE},_VITE_API_BASE_URL=${BACKEND_URL}"

gcloud run deploy "${FRONTEND_SERVICE}" \
  --image "${FRONTEND_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --concurrency "${FRONTEND_CONCURRENCY}" \
  --cpu "${FRONTEND_CPU}" \
  --memory "${FRONTEND_MEMORY}" \
  --timeout 300 \
  --max-instances "${FRONTEND_MAX_INSTANCES}" \
  --labels "app=medical-scheduling-agent,component=frontend"
