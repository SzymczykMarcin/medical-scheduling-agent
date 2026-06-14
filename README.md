# Medical Scheduling Agent

Demo system for Polish voice-based medical appointment scheduling.

The patient records a voice message in the browser. The backend transcribes the
audio, retrieves appointment-duration rules from vector RAG, asks Bielik to
extract structured scheduling intent, validates the result with deterministic
calendar logic, stores a simulated appointment, and returns an SMS-style
confirmation.

This is a demo application, not a medical device. It does not diagnose patients,
does not send real SMS messages, and does not integrate with real clinic systems.

## What Is Included

- React frontend with recording and calendar pages.
- FastAPI backend.
- `faster-whisper` speech-to-text for Polish audio.
- Bielik through an Ollama-compatible HTTP API.
- Chroma vector RAG over medical scheduling rules from `data/rag`.
- Deterministic scheduler that prevents silent calendar conflicts.
- SQLite demo calendar storage.
- Google Cloud Run deployment scripts for backend, frontend, and Bielik.

## Repository Layout

```text
backend/                 FastAPI backend and pytest suite
frontend/                React/Vite frontend
data/rag/                RAG source documents with appointment rules
deploy/cloud-run/        Google Cloud Run deployment scripts
deploy/ollama-bielik/    Bielik/Ollama Cloud Run image
tools/                   Demo smoke-test tooling
```

## Local Run Step By Step

These steps assume Windows PowerShell and a PC with a CUDA-capable GPU.

### 1. Clone The Repository

```powershell
git clone https://github.com/SzymczykMarcin/medical-scheduling-agent.git
cd medical-scheduling-agent
```

### 2. Create The Local Environment File

```powershell
Copy-Item .env.example.local-ollama .env
```

The local profile expects:

- backend: `http://127.0.0.1:8097`
- frontend: `http://localhost:5173`
- Bielik/Ollama: `http://127.0.0.1:11434`
- RAG index: `data/chroma`
- calendar database: `data/demo.sqlite3`

### 3. Start Bielik Locally

Open terminal 1:

```powershell
ollama serve
```

Open terminal 2 and download the Bielik model:

```powershell
ollama pull SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
```

Check that Bielik answers:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:11434/api/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "model": "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0",
    "messages": [{"role": "user", "content": "Odpowiedz jednym zdaniem po polsku: gotowe."}],
    "stream": false
  }'
```

### 4. Install The Backend

Open terminal 3:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
cd ..
```

### 5. Start The Backend

In terminal 3:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8097
```

### 6. Build RAG And Prewarm Models

Open terminal 4:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8097/api/rag/ingest -Method Post
Invoke-RestMethod -Uri http://127.0.0.1:8097/api/debug/prewarm -Method Post
```

The first prewarm call loads `faster-whisper` and may download the ASR model.
If Bielik, RAG, or ASR is not configured correctly, this step fails visibly.

### 7. Install And Start The Frontend

Open terminal 5:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

### 8. Run A Local Smoke Test

In terminal 4:

```powershell
python tools/run_demo_smoke.py --backend-url http://127.0.0.1:8097
```

The smoke report is written to:

```text
reports/demo_smoke_report.json
```

## Google Cloud Run Step By Step

These steps are intended for Google Cloud Shell or another shell with `gcloud`
configured.

Before starting, make sure your Google Cloud project has:

- billing enabled,
- Cloud Run GPU quota for NVIDIA L4 in the selected region,
- permission to create Cloud Run services, service accounts, IAM bindings,
  Artifact Registry repositories, and Cloud Build jobs.

### 1. Clone The Repository

```bash
git clone https://github.com/SzymczykMarcin/medical-scheduling-agent.git
cd medical-scheduling-agent
```

### 2. Select Project And Region

```bash
export PROJECT_ID="your-google-cloud-project-id"
export REGION="europe-west1"
gcloud config set project "${PROJECT_ID}"
```

Use a region where Cloud Run GPUs are available for your project.

### 3. Deploy The Whole Demo

```bash
./deploy/cloud-run/deploy-demo.sh
```

This script performs the full demo deployment:

1. Enables required Google APIs.
2. Creates the backend service account if missing.
3. Builds and deploys private Bielik/Ollama Cloud Run with NVIDIA L4 GPU.
4. Grants the backend service account access to the private Bielik service.
5. Builds and deploys the public FastAPI backend.
6. Builds and deploys the public React frontend.
7. Reconfigures backend CORS to the real frontend URL.
8. Runs RAG ingestion.
9. Runs model prewarm for Bielik and `faster-whisper`.
10. Runs a basic smoke test.
11. Prints backend, Bielik, and frontend URLs.

The first run can take a long time because Cloud Build pulls Bielik into the
model image, RAG ingestion downloads the embedding model, and prewarm downloads
or loads the ASR model. These steps are expected. If a model cannot be downloaded
or a service cannot be reached, the script fails instead of using a fake fallback.

### 4. Open The Frontend

At the end of the script, copy the printed frontend URL and open it in a browser.

The deployed frontend already contains the correct backend URL. You do not need
to edit `VITE_API_BASE_URL` manually when using `deploy-demo.sh`.

### 5. Optional Manual Checks

Use the backend URL printed by the script:

```bash
curl "https://your-backend-url/health"
curl "https://your-backend-url/api/calendar/events"
python tools/run_demo_smoke.py --backend-url "https://your-backend-url"
```

To rerun preparation after changing RAG documents:

```bash
curl -fsS -X POST "https://your-backend-url/api/rag/ingest"
curl -fsS -X POST "https://your-backend-url/api/debug/prewarm"
```

## Customizing Medical Rules

Put clinic-specific rules under `data/rag`.

Supported formats:

- Markdown
- text
- CSV
- JSONL

After changing rules, rebuild the vector index:

Local:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8097/api/rag/ingest -Method Post
```

Cloud:

```bash
curl -fsS -X POST "https://your-backend-url/api/rag/ingest"
```

The scheduler supports visit durations normalized to `30`, `60`, `90`, and
`120` minutes.

## Tests

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m pytest tests -m "not local_ai"
```

Frontend:

```powershell
cd frontend
npm run build
```

Local AI acceptance tests load real local models:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest tests -m local_ai
```

## Demo Safety Rules

- The system schedules appointments only.
- It must not diagnose patients.
- Bielik proposes structured intent, but code validates the final calendar write.
- If model output is invalid, uncertain, or conflicts with the calendar, the
  backend returns a callback-needed SMS instead of silently booking.
- Broken model, RAG, or ASR configuration should fail visibly during setup or
  testing.
