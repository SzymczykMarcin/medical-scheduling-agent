# Medical Scheduling Agent

Demo web application for voice-based appointment scheduling in Polish.

The system accepts a patient voice recording, transcribes it locally, analyzes the transcript with a Polish RAG assistant, estimates the required visit duration, finds a suitable calendar slot, and returns a short simulated SMS confirmation.

This repository is intentionally structured for a local-first demo. It avoids real telephony, real SMS delivery, and real medical decision automation.

## Product Scope

- Patient records a short voice message in the browser.
- Backend receives the audio file and runs local speech-to-text.
- Backend uses a Polish expert RAG pipeline to extract:
  - patient intent,
  - symptoms or visit reason,
  - preferred date/time constraints,
  - recommended visit duration.
- Scheduler inserts the appointment into a simulated calendar.
- Frontend shows:
  - recording page,
  - simulated calendar page,
  - short SMS-style response.

## Recommended Local AI Stack

### Polish RAG and text reasoning

Default target:

- Model: Bielik Minitron 7B v3.0 Instruct, GGUF Q4_K_M
- Runtime: `llama.cpp` through `llama-cpp-python`

The project is configured so the model path is supplied through environment variables. The current local setup can reuse the GGUF Bielik file already downloaded in `interactive-cv`; this does not reuse that project's RAG data.

### Speech transcription

Default target:

- Model: `openai/whisper-large-v3-turbo`
- Runtime: `faster-whisper` / CTranslate2
- Compute: CUDA with `int8_float16`

Whisper is not medical-grade by itself. The demo should keep transcript review visible during development and should never be represented as clinical documentation automation.

## Tech Stack

Backend:

- Python 3.11+
- FastAPI
- Pydantic Settings
- faster-whisper
- llama-cpp-python
- ChromaDB
- sentence-transformers
- SQLite for demo persistence
- pytest and ruff

Frontend:

- React
- TypeScript
- Vite
- React Router
- custom responsive CSS calendar view
- Vitest

## Repository Layout

```text
backend/
  app/
    api/              FastAPI route modules
    core/             settings and shared app configuration
    models/           Pydantic request/response schemas
    services/         ASR, RAG, scheduling, SMS simulation services
    storage/          demo persistence and seed data
    main.py           FastAPI application factory
  tests/
  pyproject.toml

frontend/
  src/
    api/              typed backend client
    components/       reusable UI components
    pages/            recorder and calendar pages
    types/            shared TypeScript types
  package.json
  vite.config.ts

docs/
  architecture.md
  requirements.md
  local-models.md

data/
  rag/                local expert documents, ignored except placeholders
  samples/            sample audio files, ignored except placeholders

models/
  README.md           where to place local GGUF and ASR model files
```

## Quick Start

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8097
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8097`.

## Environment

Copy `.env.example` to `.env` and adjust local model paths.

```powershell
Copy-Item .env.example .env
```

The default implementation can run in mock mode before downloading any model.

## API Draft

- `GET /health`
- `GET /api/calendar/events`
- `POST /api/voice/appointments`

`POST /api/voice/appointments` accepts an audio upload and returns:

- transcript,
- extracted appointment intent,
- booked calendar event,
- simulated SMS text.

## Development Notes

This is a demo scheduling assistant, not a medical device. The RAG knowledge base should explain appointment duration heuristics and triage rules, but the output should stay limited to scheduling recommendations.

Useful first milestones:

1. Run frontend with mocked backend response.
2. Run backend with mocked ASR and mocked Bielik response.
3. Enable local faster-whisper transcription with `large-v3-turbo`.
4. Add RAG documents and ChromaDB indexing.
5. Enable local Bielik Minitron 7B v3.0 Instruct GGUF inference.
6. Connect appointment insertion to the calendar page.
