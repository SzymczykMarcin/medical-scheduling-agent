# Architecture

## High-Level Flow

```mermaid
flowchart LR
    Browser["React web app"] -->|audio upload| API["FastAPI backend"]
    API --> ASR["Local ASR service"]
    ASR --> Transcript["Polish transcript"]
    Transcript --> RAG["RAG pipeline"]
    RAG --> Bielik["Bielik provider"]
    Bielik --> Intent["Structured appointment intent"]
    Intent --> Scheduler["Calendar scheduler"]
    Scheduler --> Store["SQLite demo calendar"]
    Scheduler --> Sms["Simulated SMS response"]
    Store --> Browser
    Sms --> Browser
```

## Backend Boundaries

- API layer receives files and returns typed responses.
- ASR service converts audio to transcript.
- RAG service retrieves expert knowledge through the explicitly configured backend and prompts Bielik.
- Scheduling service owns office hours, seeded appointments, and slot selection.
- SMS service formats a short confirmation message.
- Storage layer keeps demo calendar data.
- Debug API exposes a developer-only direct-vs-RAG diagnostic response without persisting raw transcripts or model outputs.

## Frontend Routes

- `/` redirects to `/record`.
- `/record` records voice and submits the scheduling request.
- `/calendar` displays seeded and newly created appointments.

## Demo Data

The calendar starts with deterministic seed appointments. Expert RAG source files live under `data/rag` and may be Markdown, text, CSV, or JSONL documents describing appointment categories, durations, and scheduling rules.

## RAG Backend Strategy

RAG backend selection is explicit through `RAG_BACKEND`:

- `chroma`: local semantic vector search with ChromaDB and sentence-transformers.
- `bigquery-vector`: cloud vector-search extension point. It is configured but not implemented yet.

Markdown/TXT/CSV/JSONL files under `data/rag` are source documents, not the retrieval backend. Structured medical rules are validated first and then indexed into a vector store before `RAG_BACKEND=chroma` can retrieve them semantically.

The backend does not silently fall back from one RAG backend to another. If `RAG_BACKEND=chroma` is selected and the Chroma store is missing, the request fails with a clear backend error instead of using non-vector retrieval.

## Debug Diagnostics

`POST /api/debug/appointment-analysis` accepts a text transcript and returns the direct Bielik output, retrieved RAG context, raw RAG Bielik output, validated intent, scheduler result, and SMS text. This endpoint is intended for development and QA. Logs should contain only metadata such as transcript length, retrieved passage count, and scheduler status.

## Model Loading Strategy

The application starts in mock mode by default. Real model loading should be lazy:

- ASR model is loaded on first transcription request.
- Bielik model is loaded on first RAG analysis request when `LLM_PROVIDER=llama-cpp`.
- Bielik is called through HTTP when `LLM_PROVIDER=ollama-http`.
- Embedding model and ChromaDB index are initialized when RAG ingestion or retrieval requires them.

This keeps startup fast and makes local demos possible before model files are available.
