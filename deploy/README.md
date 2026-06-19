# Deployment

This directory contains local and cloud deployment assets for the demo frontend,
backend, and optional local model services.

The standard Cloud Run architecture runs the API, `faster-whisper`, Bielik, and
EmbeddingGemma in one GPU backend container. The backend talks to local Ollama on
`127.0.0.1:11434`, stores RAG vectors in BigQuery, and uses BigQuery Vector
Search at query time.

The backend can use a Bielik model server when configured with:

```env
LLM_PROVIDER=ollama-http
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
```

For local development, copy:

```bash
cp .env.example.local-ollama .env
```

For Cloud Run, use `.env.example.cloud-run` as the backend environment template.

## Local Docker Compose

Start the Bielik model server:

```bash
docker compose -f deploy/docker-compose.local.yml up --build bielik-model
```

Start the embedding model server:

```bash
docker compose -f deploy/docker-compose.local.yml up --build embedding-model
```

The Bielik server listens on `http://127.0.0.1:11434`.
The embedding server listens on `http://127.0.0.1:11435`.

## Local Smoke Tests

Bielik chat:

```bash
curl http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0",
    "messages": [{"role": "user", "content": "Odpowiedz jednym zdaniem po polsku."}],
    "stream": false
  }'
```

Embedding:

```bash
curl http://127.0.0.1:11435/api/embed \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embeddinggemma:latest",
    "input": "Krótka konsultacja lekarska."
  }'
```

## Hardware Notes

- Bielik inference should use a GPU for practical latency.
- The default Cloud Run template targets one NVIDIA L4 GPU shared by the backend,
  ASR, Bielik, and embeddings.
- Embeddings are served by local Ollama in the backend container for this demo.
- Default model weights are pulled during image build and are not committed to
  this repository.
- Set `PULL_MODELS_ON_START=1` only when you intentionally override
  `OLLAMA_MODEL` or `EMBEDDING_MODEL_NAME` at runtime and want the backend to
  pull missing models during startup.

## Cloud Run

Cloud Run scripts are parameterized. They require environment variables instead of hardcoded project IDs.

The recommended self-hosted demo path is:

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west1"
./deploy/cloud-run/deploy-demo.sh
```

`deploy-demo.sh` does the glue work:

- enables required Google APIs,
- creates a backend service account when it is missing,
- grants the backend service account BigQuery permissions for the demo vector table,
- deploys the public all-in-one GPU backend Cloud Run with local Ollama,
- runs RAG ingestion into BigQuery Vector Search,
- prewarms ASR, EmbeddingGemma, and Bielik,
- deploys the React frontend as a public Cloud Run service,
- rebuilds backend CORS with the real frontend URL,
- prints backend and frontend URLs.

The first run is intentionally slower: Cloud Build pulls Bielik and
EmbeddingGemma into the backend image, RAG ingestion builds the BigQuery
vector table, and `/api/debug/prewarm` downloads/loads the ASR model. If any of
these steps fails, the command should fail visibly.

Manual deployment is still possible. Deploy the backend first:

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west1"
export FRONTEND_ORIGIN="https://your-frontend.example.com"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export EMBEDDING_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_AUTH_MODE="none"
export EMBEDDING_AUTH_MODE="none"
export RAG_BACKEND="bigquery-vector"
export RAG_INDEX_MODE="managed-vector"
export BIGQUERY_PROJECT_ID="${PROJECT_ID}"
./deploy/cloud-run/backend-cloud-run.sh
```

The backend Cloud Run script builds the repository root Dockerfile, pushes the
image to Artifact Registry, and deploys it as a public demo API. It creates the
Docker repository when it is missing. By default, the demo backend uses an
NVIDIA L4 for ASR:

```env
ASR_DEVICE=cuda
ASR_COMPUTE_TYPE=int8_float16
```

The script deploys with `min-instances=0`, so the GPU is not kept warm while the
demo is idle. The next request after idle can be slow because the container and
model need to start again.

### Cloud Smoke Checklist

After deployment, `deploy-demo.sh` already runs the basic smoke check. For a
manual full check:

```bash
curl "https://your-backend-url/health"
curl -X POST "https://your-backend-url/api/rag/ingest"
curl -X POST "https://your-backend-url/api/debug/prewarm"
curl "https://your-backend-url/api/calendar/events"
python tools/run_demo_smoke.py --backend-url "https://your-backend-url"
```

Then open the frontend URL printed by the deployment script and test a manual
recording.

For frontend builds:

```bash
cd frontend
cp .env.cloud.example .env
```

Set:

```env
VITE_API_BASE_URL=https://your-backend-service-url
```

Then build with:

```bash
npm ci
npm run build
```

### Storage Notes

The current Cloud Run profile stores RAG vectors in BigQuery Vector Search.
SQLite appointments still live under `/tmp`, which is acceptable for a
short-lived self-hosted demo but is not persistent. A more durable demo should
replace appointment storage with a managed SQL database.

The backend exposes this explicitly through:

```env
CLOUD_STORAGE_MODE=ephemeral
CALENDAR_STORAGE_BACKEND=sqlite
SQLITE_DATABASE_URL=sqlite:////tmp/medical-scheduling-agent/demo.sqlite3
```

Use `CLOUD_STORAGE_MODE=persistent` only when `DATABASE_URL` points to durable
database storage. The application validates this so a cloud deployment does not
quietly pretend that `/tmp` is persistent.

For durable appointments:

```env
CLOUD_STORAGE_MODE=persistent
CALENDAR_STORAGE_BACKEND=sql
DATABASE_URL=postgresql+psycopg://...
```

Managed vector RAG is the standard Cloud Run mode. Embeddings are generated by
local Ollama inside the backend container:

```env
RAG_BACKEND=bigquery-vector
RAG_INDEX_MODE=managed-vector
BIGQUERY_PROJECT_ID=your-project-id
BIGQUERY_DATASET_ID=rag_dataset
BIGQUERY_TABLE_ID=medical_scheduling_rules
EMBEDDING_PROVIDER=ollama-http
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL_NAME=embeddinggemma:latest
EMBEDDING_AUTH_MODE=none
```

See:

- `deploy/cloud-run/deploy-demo.sh`
- `deploy/cloud-run/backend-cloud-run.sh`
- `deploy/cloud-run/frontend-cloud-run.sh`
- `deploy/cloud-run/bielik-cloud-run.sh`
- `deploy/cloud-run/embedding-cloud-run.sh`
