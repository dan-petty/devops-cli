# Tasks

## 1. Name every planned row

Reads: `src/devops_cli/github/repo_ref.py`, `tests/github/test_repo_ref.py`.

Changes: `src/devops_cli/github/repo_ref.py`, `tests/github/test_repo_ref.py`, `docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`.

- [x] 1.1 Add the eight rows and the test, and add the Status History line.
  - Verification: `$ uv run devops ci test tests/github/test_repo_ref.py tests/docs/test_docs_adr_records.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
