# Step 1: Add Ollama HTTP LLM Provider

## Role And Standard

Act as a senior Python backend developer. Keep the code readable, typed, testable, and consistent with the existing service architecture. Write code and docstrings in English. Do not hide failures silently; errors must be logged with enough context to diagnose provider, URL, model name, and response shape problems.

## Goal

Add an explicit `ollama-http` LLM provider next to the current `llama-cpp` provider. The backend must be able to call a local or remote Ollama-compatible Bielik server without loading the model inside the backend process.

## Scope

- Extend backend settings with Ollama-specific fields:
  - `LLM_PROVIDER=llama-cpp|ollama-http`
  - `OLLAMA_BASE_URL`
  - `OLLAMA_MODEL`
  - `OLLAMA_TIMEOUT_SECONDS`
- Keep `llama-cpp` as a supported local provider.
- Add a provider abstraction if the current `BielikLlmService` becomes too provider-specific.
- Preserve existing `ConversationMessage` behavior.
- Ensure provider selection is explicit. Do not add hidden fallback between providers.

## Implementation Tasks

- Refactor `backend/app/services/bielik.py` so provider-specific code is isolated.
- Add an Ollama client that calls `/api/chat` with `stream: false`.
- Validate the response shape before returning text.
- Log generation start, provider, model, prompt size, response size, and controlled failures.
- Update `.env.example` with both provider configurations.
- Update docs for local Ollama usage only as much as needed for this step.

## Tests

- Add pytest unit tests for provider selection.
- Add tests for successful Ollama response parsing.
- Add tests for malformed Ollama responses.
- Add tests for HTTP errors and timeout handling.
- Keep tests deterministic by mocking HTTP calls.
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`

## Definition Of Done

- Backend can use `llama-cpp` exactly as before.
- Backend can use `ollama-http` through configuration.
- No model is loaded in the backend when `ollama-http` is selected.
- Tests pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Add Ollama HTTP LLM provider`.
- Push the branch.
