# Deployment

This directory contains local and cloud deployment assets for the demo backend and
model services.

The standard architecture keeps Bielik outside the backend process. The backend
calls an Ollama-compatible model service over HTTP.

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
- The default Cloud Run template targets one NVIDIA L4 GPU for Bielik.
- Embeddings may run without GPU for small demos, but GPU or a dedicated service is recommended for larger knowledge bases.
- Default model weights are pulled during image build and are not committed to this repository.
- At container startup, the entrypoint also checks the runtime `MODEL` value and pulls it if needed. This keeps model names configurable through environment variables, at the cost of a slower first startup when a non-default model is selected.

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
- deploys private Bielik Cloud Run,
- grants the backend service account `roles/run.invoker` on Bielik,
- deploys public backend Cloud Run with `OLLAMA_AUTH_MODE=google-id-token`,
- deploys the React frontend as a public Cloud Run service,
- rebuilds backend CORS with the real frontend URL,
- runs RAG ingestion,
- prewarms ASR and Bielik,
- prints backend, Bielik, and frontend URLs.

The first run is intentionally slower: Cloud Build pulls the Bielik model into
the model service image, RAG ingestion downloads the embedding model, and
`/api/debug/prewarm` downloads/loads the ASR model. If any of these downloads
fails, the command should fail visibly.

Manual deployment is still possible. Deploy the Bielik model service first:

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west1"
./deploy/cloud-run/bielik-cloud-run.sh
```

Deploy the backend after you know the Bielik service URL:

```bash
export FRONTEND_ORIGIN="https://your-frontend.example.com"
export OLLAMA_BASE_URL="https://your-bielik-service-url"
./deploy/cloud-run/backend-cloud-run.sh
```

The backend Cloud Run script builds the repository root Dockerfile, pushes the
image to Artifact Registry, and deploys it as a public demo API. It creates the
Docker repository when it is missing. By default, cloud ASR uses CPU mode:

```env
ASR_DEVICE=cpu
ASR_COMPUTE_TYPE=int8
```

This is slower than GPU transcription, but easier to deploy as a public demo. For
GPU-backed backend ASR, override those variables and adjust Cloud Run resources.

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

The current Cloud Run profile stores Chroma and SQLite under `/tmp`. That is
acceptable for a short-lived self-hosted demo, but it is not persistent. A more
durable demo should replace this with durable storage or managed vector/database
services.

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

For durable managed vector RAG:

```env
RAG_BACKEND=bigquery-vector
RAG_INDEX_MODE=managed-vector
BIGQUERY_PROJECT_ID=your-project-id
BIGQUERY_DATASET_ID=rag_dataset
BIGQUERY_TABLE_ID=medical_scheduling_rules
```

See:

- `deploy/cloud-run/deploy-demo.sh`
- `deploy/cloud-run/backend-cloud-run.sh`
- `deploy/cloud-run/frontend-cloud-run.sh`
- `deploy/cloud-run/bielik-cloud-run.sh`
- `deploy/cloud-run/embedding-cloud-run.sh`
