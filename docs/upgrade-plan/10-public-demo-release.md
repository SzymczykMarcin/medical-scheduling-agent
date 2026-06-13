# Step 10: Prepare Public Demo Release

## Role And Standard

Act as a senior release engineer. Write code, scripts, and release docs in English. Keep the repository clean, reproducible, and safe for public use. Do not commit secrets, model weights, generated reports, local databases, IDE files, or machine-specific paths.

## Goal

Prepare the repository for a public demo release that can be cloned, configured, run locally, customized with medical rules, and deployed to cloud infrastructure.

## Scope

- Final repository hygiene.
- Final documentation pass.
- Final deterministic test pass.
- Optional local AI acceptance report.
- Release checklist.

## Implementation Tasks

- Review `.gitignore`.
- Check for secrets and private paths.
- Ensure model files are excluded.
- Ensure reports and local databases are excluded.
- Confirm setup instructions use committed files only.
- Confirm deployment docs use placeholders.
- Add a release checklist document if useful.

## Tests

- Run:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`
  - `npm.cmd run build`
- Optionally run local AI acceptance tests and save the report locally.
- Verify `git status --short`.

## Definition Of Done

- Repository is clean and public-ready.
- No generated or private artifacts are staged.
- Deterministic tests/build pass.
- Documentation points to all supported run modes.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Prepare public demo release`.
- Push the branch.
