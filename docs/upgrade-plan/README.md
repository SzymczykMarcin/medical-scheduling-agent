# Upgrade Plan Index

This directory contains implementation instructions for the planned public-ready upgrade of the medical scheduling agent.

When the user asks to "implement step X", open the matching file first and follow it as the authoritative checklist for that step.

## Steps

1. [Add Ollama HTTP LLM Provider](01-ollama-http-llm-provider.md)
2. [Add Local And Cloud Model Servers](02-local-and-cloud-model-servers.md)
3. [Standardize RAG Backends](03-standardize-rag-backends.md)
4. [Build Medical Rules Ingestion](04-medical-rules-ingestion.md)
5. [Add Direct vs RAG Debug Flow](05-direct-vs-rag-debug-flow.md)
6. [Add Cloud-Ready Runtime Profiles](06-cloud-ready-runtime-profiles.md)
7. [Rewrite Public README](07-public-readme.md)
8. [Harden LLM JSON Contracts](08-harden-llm-json-contracts.md)
9. [Expand RAG And Scheduler Quality Tests](09-rag-scheduler-quality-tests.md)
10. [Prepare Public Demo Release](10-public-demo-release.md)

## Global Rules

- Act as a senior software engineer responsible for a public repository.
- Keep implementation code in English.
- Keep user-facing Polish behavior where the product currently uses Polish.
- Prefer clear, small, testable changes over broad rewrites.
- Preserve the stable branch and avoid using personal assistant branding in branches, commits, docs, or code.
- End each implementation step with verification, a clean Git status, a commit, and a push.
