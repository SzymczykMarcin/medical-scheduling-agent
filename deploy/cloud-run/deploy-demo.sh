#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"
: "${FRONTEND_ORIGIN:?Set FRONTEND_ORIGIN to the public frontend URL or local preview origin.}"

: "${BIELIK_SERVICE:=medical-scheduling-bielik}"
: "${BACKEND_SERVICE:=medical-scheduling-backend}"
: "${BACKEND_SERVICE_ACCOUNT:=medical-scheduling-backend}"
: "${RUN_SMOKE_TEST:=1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_SERVICE_ACCOUNT_EMAIL="${BACKEND_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "${PROJECT_ID}"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com

if ! gcloud iam service-accounts describe "${BACKEND_SERVICE_ACCOUNT_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${BACKEND_SERVICE_ACCOUNT}" \
    --display-name "Medical Scheduling Backend"
fi

"${SCRIPT_DIR}/bielik-cloud-run.sh"

BIELIK_URL="$(gcloud run services describe "${BIELIK_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"

gcloud run services add-iam-policy-binding "${BIELIK_SERVICE}" \
  --region "${REGION}" \
  --member "serviceAccount:${BACKEND_SERVICE_ACCOUNT_EMAIL}" \
  --role "roles/run.invoker"

OLLAMA_BASE_URL="${BIELIK_URL}" \
OLLAMA_AUTH_MODE="google-id-token" \
BACKEND_SERVICE="${BACKEND_SERVICE}" \
BACKEND_SERVICE_ACCOUNT_EMAIL="${BACKEND_SERVICE_ACCOUNT_EMAIL}" \
"${SCRIPT_DIR}/backend-cloud-run.sh"

BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"

echo "Backend URL: ${BACKEND_URL}"
echo "Bielik URL: ${BIELIK_URL}"
echo "Frontend env:"
echo "VITE_API_BASE_URL=${BACKEND_URL}"

if [ "${RUN_SMOKE_TEST}" = "1" ]; then
  python "${REPO_ROOT}/tools/run_demo_smoke.py" \
    --backend-url "${BACKEND_URL}" \
    --basic-only
fi
