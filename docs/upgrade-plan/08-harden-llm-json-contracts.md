# Step 8: Harden LLM JSON Contracts

## Role And Standard

Act as a senior Python backend developer specializing in reliable LLM integrations. Write code in English. Treat LLM output as untrusted input. Validate everything before scheduling an appointment.

## Goal

Make Bielik's structured output more reliable and safer by versioning schemas, validating strictly, and adding controlled repair behavior where appropriate.

## Scope

- Version the appointment intent schema.
- Improve prompt clarity.
- Add strict parsing and validation.
- Optionally add one repair attempt for malformed JSON.
- Ensure low-confidence or contradictory responses result in callback, not booking.

## Implementation Tasks

- Add schema version to prompt and response models.
- Improve JSON extraction and validation errors.
- Add a repair prompt only for syntax-level JSON issues, not semantic uncertainty.
- Add confidence thresholds in deterministic code.
- Log raw LLM output only in debug-safe paths.
- Keep patient-facing SMS deterministic.

## Tests

- Add pytest tests for:
  - valid JSON
  - fenced JSON
  - malformed JSON repaired once
  - contradictory preferences
  - low confidence
  - unsupported duration
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`

## Definition Of Done

- Invalid or uncertain LLM responses do not create appointments.
- Valid responses still schedule normally.
- Tests pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Harden appointment intent JSON contracts`.
- Push the branch.
