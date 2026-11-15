# Tasks

## 1. Retry a rate limit and a capacity limit

Reads: `src/devops_cli/ai/providers/__init__.py`, `src/devops_cli/config/constants.py`, `pydantic_ai/retries.py`.

Changes: `src/devops_cli/ai/providers/__init__.py`, `src/devops_cli/config/constants.py`, `tests/ai/test_jev_retry.py`.

- [x] 1.1 Write the four cases and watch them fail.
  - Verification: `$ uv run devops ci test tests/ai/test_jev_retry.py`
- [x] 1.2 Add the transport and the attempt constant.
  - Verification: `$ uv run devops ci test tests/ai/test_jev_retry.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
