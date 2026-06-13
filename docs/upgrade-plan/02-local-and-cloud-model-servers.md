# Step 2: Add Local And Cloud Model Servers

## Role And Standard

Act as a senior backend and platform engineer. Keep deployment files clear, minimal, and reproducible. Write scripts, comments, and documentation in English. Prefer explicit environment variables and predictable ports. Avoid personal assistant branding in filenames, branches, labels, and images.

## Goal

Provide reusable model-server deployment assets for Bielik and the embedding model. The project should support local Docker/Ollama usage and a cloud deployment path inspired by the training repository.

## Scope

- Add deployment assets under `deploy/`.
- Support a Bielik Ollama server.
- Support an embedding Ollama server or document why the first version keeps embeddings in-process.
- Add local Docker Compose for model servers and backend wiring.
- Add Cloud Run deployment scripts or templates.

## Implementation Tasks

- Create:
  - `deploy/ollama-bielik/Dockerfile`
  - `deploy/ollama-embedding/Dockerfile`
  - `deploy/docker-compose.local.yml`
  - `deploy/cloud-run/bielik-cloud-run.sh`
  - `deploy/cloud-run/embedding-cloud-run.sh`
- Configure model keep-alive behavior for server mode.
- Use neutral labels and image names.
- Document required GPU and memory assumptions.
- Keep model names configurable through environment variables.
- Do not commit model weights.

## Tests

- Add lightweight validation tests for generated configuration files if practical.
- Add a script or documented smoke command for:
  - Ollama Bielik `/api/chat`
  - embedding `/api/embed`
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`
  - `npm.cmd run build`

## Definition Of Done

- A developer can start local model servers from documented commands.
- Cloud Run scripts are parameterized and do not contain private project IDs.
- README or step docs explain model download behavior.
- Tests/build pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Add model server deployment assets`.
- Push the branch.
