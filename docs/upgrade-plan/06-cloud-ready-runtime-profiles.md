# Step 6: Add Cloud-Ready Runtime Profiles

## Role And Standard

Act as a senior platform engineer. Write configuration and docs in English. Keep runtime profiles explicit, reproducible, and safe for a public repository. Do not include secrets, private project IDs, or machine-specific paths in committed examples.

## Goal

Provide clear runtime profiles for local and cloud usage.

## Scope

Create documented profiles:

- `local-cpu`
- `local-gpu`
- `local-ollama`
- `cloud-run`
- `cloud-run-with-vector-store`

## Implementation Tasks

- Add example environment files:
  - `.env.example.local-cpu`
  - `.env.example.local-gpu`
  - `.env.example.local-ollama`
  - `.env.example.cloud-run`
- Ensure settings support all profile values.
- Remove hardcoded private machine paths from default public examples.
- Document required model paths or model server URLs.
- Add health checks that reveal selected profile without leaking secrets.

## Tests

- Add tests for settings parsing for each profile.
- Add tests that missing required settings fail with clear errors when the selected provider needs them.
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`
  - `npm.cmd run build`

## Definition Of Done

- A new user can choose a profile without reading source code.
- Public examples contain no private paths or secrets.
- Tests/build pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Add runtime profile configuration`.
- Push the branch.
