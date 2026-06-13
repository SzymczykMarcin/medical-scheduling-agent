# Step 7: Rewrite Public README

## Role And Standard

Act as a senior technical writer and full-stack engineer. Write the README in clear English for a public repository. Keep instructions honest, reproducible, and beginner-friendly without hiding hardware requirements.

## Goal

Rewrite the project README so a new user can understand, run, test, deploy, and customize the demo.

## Scope

The README must cover:

- project purpose
- architecture
- local quick start
- local GPU setup
- Ollama model-server setup
- cloud deployment overview
- replacing medical rules
- running tests
- troubleshooting
- privacy and demo limitations

## Implementation Tasks

- Replace vague setup text with step-by-step commands.
- Include a simple architecture diagram.
- Explain that model weights are not stored in the repository.
- Explain how to configure Bielik and transcription models.
- Link to detailed docs under `docs/`.
- Keep Polish product behavior clearly described.

## Tests

- Run command snippets that are safe and local where practical.
- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`
  - `npm.cmd run build`

## Definition Of Done

- README is usable by someone who has not seen the project before.
- No private local paths are presented as defaults.
- Setup instructions match actual project files.
- Tests/build pass.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Rewrite public project README`.
- Push the branch.
