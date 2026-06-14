#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID.}"
: "${REGION:?Set REGION, for example europe-west1.}"

: "${BIELIK_SERVICE:=medical-scheduling-bielik}"
: "${EMBEDDING_SERVICE:=medical-scheduling-embedding}"
: "${BACKEND_SERVICE:=medical-scheduling-backend}"
: "${FRONTEND_SERVICE:=medical-scheduling-frontend}"
: "${BACKEND_SERVICE_ACCOUNT:=medical-scheduling-backend}"
: "${FRONTEND_ORIGIN:=http://localhost:5173}"
: "${RUN_RAG_INGEST:=1}"
: "${RUN_MODEL_PREWARM:=1}"
: "${RUN_SMOKE_TEST:=1}"
: "${REPLACE_EXISTING_SERVICES:=0}"

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
  iam.googleapis.com \
  bigquery.googleapis.com

if [ "${REPLACE_EXISTING_SERVICES}" = "1" ]; then
  echo "Replacing existing Cloud Run demo services before deploy."
  for service in "${FRONTEND_SERVICE}" "${BACKEND_SERVICE}" "${BIELIK_SERVICE}" "${EMBEDDING_SERVICE}"; do
    if gcloud run services describe "${service}" --region "${REGION}" >/dev/null 2>&1; then
      gcloud run services delete "${service}" --region "${REGION}" --quiet
    fi
  done
fi

if ! gcloud iam service-accounts describe "${BACKEND_SERVICE_ACCOUNT_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${BACKEND_SERVICE_ACCOUNT}" \
    --display-name "Medical Scheduling Backend"
fi

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${BACKEND_SERVICE_ACCOUNT_EMAIL}" \
  --role "roles/bigquery.jobUser" \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${BACKEND_SERVICE_ACCOUNT_EMAIL}" \
  --role "roles/bigquery.dataEditor" \
  --quiet >/dev/null

"${SCRIPT_DIR}/bielik-cloud-run.sh"
"${SCRIPT_DIR}/embedding-cloud-run.sh"

BIELIK_URL="$(gcloud run services describe "${BIELIK_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"
EMBEDDING_URL="$(gcloud run services describe "${EMBEDDING_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"

gcloud run services add-iam-policy-binding "${BIELIK_SERVICE}" \
  --region "${REGION}" \
  --member "serviceAccount:${BACKEND_SERVICE_ACCOUNT_EMAIL}" \
  --role "roles/run.invoker"

gcloud run services add-iam-policy-binding "${EMBEDDING_SERVICE}" \
  --region "${REGION}" \
  --member "serviceAccount:${BACKEND_SERVICE_ACCOUNT_EMAIL}" \
  --role "roles/run.invoker"

echo "Deploying GPU demo profile: Bielik on L4, backend ASR on L4, min instances 0, max instances 1."

OLLAMA_BASE_URL="${BIELIK_URL}" \
OLLAMA_AUTH_MODE="google-id-token" \
EMBEDDING_BASE_URL="${EMBEDDING_URL}" \
EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-ollama-http}" \
EMBEDDING_MODEL_NAME="${EMBEDDING_MODEL_NAME:-embeddinggemma:latest}" \
EMBEDDING_AUTH_MODE="${EMBEDDING_AUTH_MODE:-google-id-token}" \
RAG_BACKEND="${RAG_BACKEND:-bigquery-vector}" \
RAG_INDEX_MODE="${RAG_INDEX_MODE:-managed-vector}" \
BIGQUERY_PROJECT_ID="${BIGQUERY_PROJECT_ID:-${PROJECT_ID}}" \
BACKEND_SERVICE="${BACKEND_SERVICE}" \
BACKEND_SERVICE_ACCOUNT_EMAIL="${BACKEND_SERVICE_ACCOUNT_EMAIL}" \
FRONTEND_ORIGIN="${FRONTEND_ORIGIN}" \
BACKEND_GPU_ENABLED="${BACKEND_GPU_ENABLED:-true}" \
BACKEND_GPU_TYPE="${BACKEND_GPU_TYPE:-nvidia-l4}" \
BACKEND_CPU="${BACKEND_CPU:-4}" \
BACKEND_MEMORY="${BACKEND_MEMORY:-16Gi}" \
BACKEND_CONCURRENCY="${BACKEND_CONCURRENCY:-1}" \
BACKEND_MIN_INSTANCES="${BACKEND_MIN_INSTANCES:-0}" \
BACKEND_MAX_INSTANCES="${BACKEND_MAX_INSTANCES:-1}" \
ASR_DEVICE="${ASR_DEVICE:-cuda}" \
ASR_COMPUTE_TYPE="${ASR_COMPUTE_TYPE:-int8_float16}" \
"${SCRIPT_DIR}/backend-cloud-run.sh"

BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"

echo "Preparing backend before exposing the frontend."
echo "Backend URL: ${BACKEND_URL}"
echo "Bielik URL: ${BIELIK_URL}"
echo "Embedding URL: ${EMBEDDING_URL}"

if [ "${RUN_RAG_INGEST}" = "1" ]; then
  echo "Building RAG index. The frontend URL will be printed only after this succeeds."
  curl -fsS -X POST "${BACKEND_URL}/api/rag/ingest"
fi

if [ "${RUN_MODEL_PREWARM}" = "1" ]; then
  echo "Prewarming ASR and Bielik. The frontend URL will be printed only after this succeeds."
  curl -fsS -X POST "${BACKEND_URL}/api/debug/prewarm"
fi

if [ "${RUN_SMOKE_TEST}" = "1" ]; then
  echo "Running backend smoke test before frontend deployment."
  python "${REPO_ROOT}/tools/run_demo_smoke.py" \
    --backend-url "${BACKEND_URL}" \
    --basic-only
fi

echo "Backend preparation completed. Deploying frontend."

BACKEND_URL="${BACKEND_URL}" \
FRONTEND_SERVICE="${FRONTEND_SERVICE}" \
"${SCRIPT_DIR}/frontend-cloud-run.sh"

FRONTEND_URL="$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)")"

gcloud run services update "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --update-env-vars "CORS_ORIGINS=${FRONTEND_URL}"

echo "Demo deployment completed successfully."
echo "Backend URL: ${BACKEND_URL}"
echo "Bielik URL: ${BIELIK_URL}"
echo "Embedding URL: ${EMBEDDING_URL}"
echo "Frontend URL: ${FRONTEND_URL}"
