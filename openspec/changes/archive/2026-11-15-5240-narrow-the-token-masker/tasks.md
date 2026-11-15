# Tasks

## 1. Keep a name after a keyword

Reads: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`.

Changes: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`.

- [x] 1.1 Add the two negative cases and watch them fail.
  - Verification: `$ uv run devops ci test tests/security/test_secret_redaction.py`
- [x] 1.2 Narrow the space-separated rule and keep every positive case.
  - Verification: `$ uv run devops ci test tests/security/test_secret_redaction.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
