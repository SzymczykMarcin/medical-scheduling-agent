# Architecture

## High-Level Flow

```mermaid
flowchart LR
    Browser["React web app"] -->|audio upload| API["FastAPI backend"]
    API --> ASR["Local ASR service"]
    ASR --> Transcript["Polish transcript"]
    Transcript --> RAG["RAG pipeline"]
    RAG --> Bielik["Local Bielik GGUF"]
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
- RAG service retrieves local expert knowledge and prompts Bielik.
- Scheduling service owns office hours, seeded appointments, and slot selection.
- SMS service formats a short confirmation message.
- Storage layer keeps demo calendar data.

## Frontend Routes

- `/` redirects to `/record`.
- `/record` records voice and submits the scheduling request.
- `/calendar` displays seeded and newly created appointments.

## Demo Data

The calendar starts with deterministic seed appointments. Expert RAG files live under `data/rag` and should be plain Markdown or text documents describing appointment categories, durations, and scheduling rules.

## Model Loading Strategy

The application starts in mock mode by default. Real model loading should be lazy:

- ASR model is loaded on first transcription request.
- Bielik model is loaded on first RAG analysis request.
- Embedding model and ChromaDB index are initialized when RAG indexing is requested.

This keeps startup fast and makes local demos possible before model files are available.
