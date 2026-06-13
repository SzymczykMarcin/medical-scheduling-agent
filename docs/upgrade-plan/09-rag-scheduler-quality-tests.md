# Step 9: Expand RAG And Scheduler Quality Tests

## Role And Standard

Act as a senior QA automation engineer and Python developer. Follow ISTQB principles: tests must be traceable, repeatable, deterministic where possible, and clear about expected behavior. Write test code in English. Keep Polish transcripts where they represent product behavior.

## Goal

Expand the acceptance and integration test suite for the RAG, Bielik, and scheduler flow.

## Scope

- Keep fast deterministic tests separate from local AI tests.
- Improve HTML reports.
- Add more edge cases for Polish scheduling language.
- Add traceability from requirement/case ID to expected result.

## Implementation Tasks

- Add or refine acceptance cases for:
  - exact occupied slot
  - exact free slot
  - flexible day preference
  - multiple day preference
  - excluded day
  - no duration clue
  - too much information
  - missing preferred time
  - urgent symptoms requiring callback
- Include input, expected output, actual output, and pass/fail in the report.
- Ensure local AI tests release resources after completion where practical.
- Keep model-loading tests opt-in.

## Tests

- Run deterministic tests:
  - `python -m ruff check backend`
  - `python -m pytest backend\tests -m "not local_ai"`
- Run local AI acceptance tests only when explicitly requested:
  - `python backend\tools\run_bielik_acceptance_tests.py`

## Definition Of Done

- Test cases are documented and traceable.
- Report is saved under `reports/`.
- Deterministic test suite passes.
- Local AI suite can be run manually and produces an HTML report.
- Git status is reviewed.
- Commit with a clear neutral message, for example `Expand RAG scheduler quality tests`.
- Push the branch.
