# Medical RAG Source Rules

This directory contains active clinic knowledge used to build the vector RAG index.

## Active Sources

Files directly under `data/rag/` are treated as active RAG sources.

Supported active formats:

- `.md`
- `.txt`
- `.csv`
- `.jsonl`

Markdown and text files without structured rule fields are accepted as legacy source documents.
CSV, JSONL, and structured Markdown are validated as medical scheduling rules before indexing.

## Examples And Schema

- `examples/` contains optional starter datasets. These files are not indexed by default.
- `schema/medical_rule.schema.json` documents the structured rule shape.

To use an example, copy it from `examples/` into `data/rag/` or point `RAG_DOCUMENT_DIR` to your own active rules directory.

## Structured Fields

Required:

- `procedure_name`
- `specialty`
- `duration_minutes`
- `duration_rationale`

Optional:

- `patient_preparation`
- `contraindications_for_auto_booking`
- `source`

`duration_minutes` is normalized up to one of the scheduler-supported values: `30`, `60`, `90`, `120`.

After editing rules, rebuild the vector index through:

```text
POST /api/rag/ingest
```
