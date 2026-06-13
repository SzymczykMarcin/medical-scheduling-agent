# Step 4: Build Medical Rules Ingestion

## Role And Standard

Act as a senior Python backend developer with strong data validation discipline. Write code in English. Treat medical scheduling rules as user-editable knowledge assets that must be validated before indexing. Keep error messages actionable.

## Goal

Make it easy to replace or extend medical rules for a clinic or specialty. Support structured ingestion from Markdown, CSV, and JSONL where practical.

## Scope

- Define a stable rule schema.
- Add example rule datasets for multiple specialties.
- Validate rules before indexing.
- Provide a clear ingestion API and/or CLI.
- Keep Polish medical content in Polish, but code and schema names in English.

## Implementation Tasks

- Add a rule model, for example:
  - `procedure_name`
  - `specialty`
  - `duration_minutes`
  - `duration_rationale`
  - `patient_preparation`
  - `contraindications_for_auto_booking`
  - `source`
- Add sample files under `data/rag/examples/`.
- Add schema documentation under `data/rag/schema/`.
- Extend ingestion to report invalid rows with line/file context.
- Make ingestion idempotent where possible.

## Tests

- Add pytest tests for valid and invalid Markdown/CSV/JSONL inputs.
- Add tests for duration normalization to `30`, `60`, `90`, `120`.
- Add tests for clear validation errors.
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`

## Definition Of Done

- A user can replace demo rules without editing Python code.
- Invalid rules fail loudly with useful messages.
- Ingestion creates retrievable chunks.
- Tests pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Add medical rules ingestion`.
- Push the branch.
