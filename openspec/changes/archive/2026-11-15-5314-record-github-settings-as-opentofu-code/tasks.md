# Tasks

## 1. Write the record

Reads: `docs/adr/README.md`, `docs/adr/0025-...`.

Changes: `docs/adr/0026-github-settings-live-in-opentofu-code-and-the-owner-applies-it.md`, `docs/adr/README.md`.

- [x] 1.1 Write the record with its front matter and body hash, and regenerate the index.
  - Verification: `$ uv run devops ci test tests/docs/test_docs_adr_records.py`

## Workflow follow-up

- Pending a person: apply the first settings change with the record.
