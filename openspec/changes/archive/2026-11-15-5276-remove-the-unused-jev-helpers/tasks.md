# Tasks

## 1. Remove the unused helpers

Reads: `src/devops_cli/ai/jev.py`, `tests/ai/test_jev.py`, `tests/ai/test_jev_one_model_many_requests.py`.

Changes: `src/devops_cli/ai/jev.py`, `tests/ai/test_jev.py`, `tests/ai/test_jev_one_model_many_requests.py`, `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md`, `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`.

- [x] 1.1 Remove the five functions, their types and tests, and keep the auto mode test.
  - Verification: `$ uv run devops ci test tests/ai`
- [x] 1.2 Add the Status History lines.
  - Verification: `$ uv run devops ci test tests/docs/test_docs_adr_records.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
