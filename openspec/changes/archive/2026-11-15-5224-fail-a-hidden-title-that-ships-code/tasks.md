# Tasks

## 1. Refuse a hidden type that ships code

Reads: `.github/workflows/pr-title.yml`, `release-please-config.json`, `CONTRIBUTING.md`.

Changes: `src/devops_cli/github/release_title.py`, `.github/workflows/pr-title.yml`, `CONTRIBUTING.md`, `tests/github/test_release_title.py`, `tests/invariants/test_workflow_contracts.py`.

- [x] 1.1 Write the five cases and watch them fail.
  - Verification: `$ uv run devops ci test tests/github/test_release_title.py`
- [x] 1.2 Add the module, the workflow step and the CONTRIBUTING rule.
  - Verification: `$ uv run devops ci test tests/github/test_release_title.py tests/invariants/test_workflow_contracts.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
