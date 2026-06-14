#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"

: "${BIELIK_SERVICE:=medical-scheduling-bielik}"
: "${BACKEND_SERVICE:=medical-scheduling-backend}"
: "${FRONTEND_SERVICE:=medical-scheduling-frontend}"
: "${BACKEND_SERVICE_ACCOUNT:=medical-scheduling-backend}"
: "${FRONTEND_ORIGIN:=http://localhost:5173}"
: "${RUN_RAG_INGEST:=1}"
: "${RUN_MODEL_PREWARM:=1}"
: "${RUN_SMOKE_TEST:=1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_SERVICE_ACCOUNT_EMAIL="${BACKEND_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"

if [ "${PROJECT_ID}" = "your-google-cloud-project-id" ] || [ "${PROJECT_ID}" = "your-project-id" ]; then
  echo "PROJECT_ID is still a placeholder: ${PROJECT_ID}" >&2
  echo "Run: gcloud projects list --format='table(projectId,name,projectNumber)'" >&2
  echo "Then set PROJECT_ID to a real projectId value, not the example text." >&2
  exit 2
fi

if ! gcloud projects describe "${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Cannot access Google Cloud project: ${PROJECT_ID}" >&2
  echo "Check that the project exists and your active gcloud account has access." >&2
  echo "Useful commands:" >&2
  echo "  gcloud auth list" >&2
  echo "  gcloud projects list --format='table(projectId,name,projectNumber)'" >&2
  exit 2
fi

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
FRONTEND_ORIGIN="${FRONTEND_ORIGIN}" \
"${SCRIPT_DIR}/backend-cloud-run.sh"

BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"

BACKEND_URL="${BACKEND_URL}" \
FRONTEND_SERVICE="${FRONTEND_SERVICE}" \
"${SCRIPT_DIR}/frontend-cloud-run.sh"

FRONTEND_URL="$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"

gcloud run services update "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --update-env-vars "CORS_ORIGINS=${FRONTEND_URL}"

echo "Backend URL: ${BACKEND_URL}"
echo "Bielik URL: ${BIELIK_URL}"
echo "Frontend URL: ${FRONTEND_URL}"

if [ "${RUN_RAG_INGEST}" = "1" ]; then
  curl -fsS -X POST "${BACKEND_URL}/api/rag/ingest"
fi

if [ "${RUN_MODEL_PREWARM}" = "1" ]; then
  curl -fsS -X POST "${BACKEND_URL}/api/debug/prewarm"
fi

if [ "${RUN_SMOKE_TEST}" = "1" ]; then
  python "${REPO_ROOT}/tools/run_demo_smoke.py" \
    --backend-url "${BACKEND_URL}" \
    --basic-only
fi
