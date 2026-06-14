# Demo Quality Evaluation

This project is a demo, so quality checks focus on repeatable behavior instead
of production monitoring.

## Smoke Test

Run this when the backend is already started:

```powershell
python tools/run_demo_smoke.py --backend-url http://127.0.0.1:8097
```

The script checks:

- `/health`
- `/api/calendar/events`
- `/api/rag/ingest`
- `/api/debug/appointment-analysis`

It writes a JSON report to:

```text
reports/demo_smoke_report.json
```

Use `--basic-only` for an immediate post-deploy connectivity check. This checks
only `/health` and `/api/calendar/events`, so it is safe to run before the RAG
index or the model service has warmed up.

Use `--skip-rag-ingest` when the vector index is managed externally and should
not be rebuilt during the smoke test.

## Local AI Acceptance Report

Run this when local Bielik, embeddings, RAG data, and scheduler are configured:

```powershell
cd backend
python tools/run_bielik_acceptance_tests.py
```

The script writes a self-contained HTML report to:

```text
reports/bielik_rag_scheduler_pytest.html
```

The report compares Polish scheduling inputs with expected and actual behavior.
This is the right place to improve demo quality when model interpretation changes.
