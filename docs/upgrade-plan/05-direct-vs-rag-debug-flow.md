# Step 5: Add Direct vs RAG Debug Flow

## Role And Standard

Act as a senior backend developer and QA-minded AI engineer. Write code in English. Keep debug endpoints clearly separated from patient-facing endpoints. Never expose raw debug internals in production UI unless explicitly configured.

## Goal

Add a diagnostic flow that compares Bielik without RAG, Bielik with RAG, retrieved context, validated intent, and scheduler decision.

## Scope

- Add a debug API endpoint, for example `POST /api/debug/appointment-analysis`.
- Add debug response models.
- Keep the existing patient flow unchanged.
- Make this endpoint configurable or clearly documented as development-only.

## Implementation Tasks

- Add request model accepting transcript text and optional date/calendar overrides.
- Return:
  - direct Bielik output
  - RAG passages
  - RAG Bielik raw output
  - validated intent
  - scheduler result
  - final SMS text
- Use existing services where possible.
- Add logs that help identify whether failure came from retrieval, generation, validation, or scheduling.

## Tests

- Add pytest tests using mocked LLM and retriever.
- Add tests for successful debug response.
- Add tests for invalid LLM JSON.
- Add tests for scheduler callback result.
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`

## Definition Of Done

- Developers can inspect the full AI scheduling decision path.
- The production appointment endpoint still returns the current stable response shape.
- Tests pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Add appointment analysis debug flow`.
- Push the branch.
