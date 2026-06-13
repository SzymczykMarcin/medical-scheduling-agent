# Model Server Deployment

This directory contains local and cloud deployment assets for serving models outside the backend process.

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

## Smoke Tests

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

See:

- `deploy/cloud-run/bielik-cloud-run.sh`
- `deploy/cloud-run/embedding-cloud-run.sh`
