# Step 3: Standardize RAG Backends

## Role And Standard

Act as a senior Python backend developer and RAG system designer. Keep interfaces small and explicit. Write code in English. Make backend selection deterministic and configurable. Do not use hidden fallbacks for production behavior; fallback behavior may exist only as an intentional demo mode with clear logs.

## Goal

Turn the current RAG retrieval behavior into a clean provider system with documented backends:

- `file`
- `chroma`
- `bigquery-vector` or equivalent cloud vector store

## Scope

- Define one retrieval protocol used by the appointment pipeline.
- Keep local file retrieval for simple demos.
- Keep Chroma for local vector search.
- Add a cloud vector-store interface and implementation plan.
- Ensure retrieved passages include source metadata.

## Implementation Tasks

- Refactor `backend/app/services/rag_retrieval.py` into provider-specific classes if needed.
- Add settings for cloud vector-store configuration without requiring cloud dependencies in local mode.
- Keep import boundaries clean so local mode does not import cloud SDKs.
- Add structured logging for selected backend, query size, result count, and source labels.
- Update RAG ingestion to target the selected backend where appropriate.

## Tests

- Add unit tests for backend selection.
- Add tests for file retrieval ordering.
- Add tests for Chroma retrieval using mocks.
- Add tests that cloud backend is not imported in file mode.
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`

## Definition Of Done

- RAG backend selection is explicit and documented.
- Existing file-based demo remains stable.
- Chroma behavior is still available.
- Cloud vector-store integration has a clean extension point.
- Tests pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Standardize RAG backend providers`.
- Push the branch.
