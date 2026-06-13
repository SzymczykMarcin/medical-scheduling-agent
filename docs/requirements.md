# Requirements

## Goal

Build a local-first demo system for scheduling medical appointments from Polish voice recordings. The demo must show the full user journey without real phone calls, real SMS delivery, or real clinic system integration.

## Functional Requirements

### Voice recording

- The user can record audio in the browser.
- The user can play back the recorded audio before sending it.
- The frontend sends the recording to the backend as a file upload.
- Supported browser audio format for MVP: WebM/Opus.

### Transcription

- The backend transcribes Polish speech locally.
- The transcription service exposes a stable interface around the chosen local model.
- MVP transcription can run in mock mode.
- Target implementation uses `faster-whisper` with `large-v3-turbo`.

### Text analysis and RAG

- The backend analyzes the transcript in Polish.
- The RAG pipeline retrieves appointment duration and scheduling guidance from the explicitly configured knowledge backend.
- The LLM extracts structured appointment intent:
  - visit reason,
  - urgency level for scheduling purposes,
  - preferred date/time,
  - estimated visit duration,
  - short explanation.
- Target LLM uses either a local quantized Bielik model through `llama-cpp-python` or an explicit Ollama-compatible HTTP model server.

### Scheduling

- The backend stores a simulated calendar.
- The backend finds the earliest available slot matching:
  - requested date/time preferences when possible,
  - estimated visit duration,
  - configured office hours,
  - existing simulated appointments.
- The backend inserts the new appointment and returns it to the frontend.

### SMS simulation

- The backend returns a short SMS-style confirmation in Polish.
- No real SMS provider is used.

### Frontend calendar

- The frontend displays seeded appointments.
- After a successful voice scheduling request, the new appointment appears in the calendar.

## Non-Functional Requirements

- Runs on a single developer PC.
- Keeps AI model paths, model server URLs, and RAG backends configurable by environment variables.
- Supports mock mode only for early development before local models are downloaded.
- Avoids sending patient audio or text to external services.
- Uses English documentation and code comments.
- Keeps medical claims conservative: the assistant schedules visits, it does not diagnose.

## Backend Library Choices

- `fastapi`: HTTP API and file upload handling.
- `uvicorn`: ASGI development server.
- `pydantic-settings`: typed environment configuration.
- `python-multipart`: multipart audio uploads.
- `faster-whisper`: local Whisper inference using CTranslate2.
- `llama-cpp-python`: local GGUF Bielik inference.
- Ollama-compatible HTTP API: optional Bielik model-server mode.
- `chromadb`: optional local vector store for RAG.
- `sentence-transformers`: local embedding model runtime.
- `sqlmodel`: lightweight SQLite persistence for demo appointments.
- `ruff`: linting and formatting.
- `pytest`: backend tests.

## Frontend Library Choices

- `react`: UI framework.
- `typescript`: safer API and calendar data contracts.
- `vite`: fast dev server and build tool.
- `react-router-dom`: recorder and calendar routes.
- Custom CSS calendar view: lightweight empty state until backend appointment data is available.
- `lucide-react`: icon set.
- `vitest`: frontend unit tests.

## Local Model Choices

### Bielik

Target model:

| Model | Quantization | Runtime |
| --- | --- | --- |
| Bielik Minitron 7B v3.0 Instruct | GGUF Q4_K_M | llama.cpp / llama-cpp-python |

Use GGUF builds and `llama.cpp` because they are practical for local Windows demos and allow CPU/GPU mixed inference. Use `LLM_PROVIDER=ollama-http` when Bielik is served by a local or cloud model server.

## RAG Backend Choices

| Backend | Purpose | Status |
| --- | --- | --- |
| `chroma` | Local semantic vector search | Default |
| `bigquery-vector` | Cloud vector-search extension point | Configured, not implemented |

Backend selection must be explicit. The system must not silently switch from a broken vector store to non-vector retrieval, because that would hide configuration failures during testing. Markdown/TXT files are source documents for ingestion, not a replacement for vector retrieval.

### Transcription

Target model:

| Model | Runtime | Compute type |
| --- | --- | --- |
| Whisper large-v3-turbo | faster-whisper / CTranslate2 | CUDA `int8_float16` |

## Out of Scope

- Real phone calls.
- Real SMS sending.
- Real electronic medical record integration.
- Medical diagnosis.
- Production authentication and authorization.
- Production-grade audit logging.

## References

- Bielik 11B v2 Technical Report: https://arxiv.org/abs/2505.02410
- Bielik 11B v3 Technical Report: https://arxiv.org/abs/2601.11579
- Bielik v3 7B and 11B tokenizer optimization report: https://arxiv.org/abs/2604.10799
- Bielik Minitron 7B report: https://arxiv.org/abs/2603.11881
- OpenAI Whisper repository: https://github.com/openai/whisper
- faster-whisper repository: https://github.com/SYSTRAN/faster-whisper
