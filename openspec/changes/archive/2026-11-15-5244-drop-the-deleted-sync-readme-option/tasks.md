# Tasks

## 1. State the command that works

Reads: `docs/adr/README.md`, `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`.

Changes: `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`.

- [x] 1.1 Add the dated line to each record.
  - Verification: `$ uv run devops ci test tests/docs/test_docs_adr_records.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
