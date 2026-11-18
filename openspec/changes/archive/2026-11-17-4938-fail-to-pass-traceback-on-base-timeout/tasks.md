# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for a base timeout, a head timeout and a gate-row timeout.
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.2 Catch the timeout in `_run_pytest_replay` and carry its limit in the result.
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.3 Print the limit and files without a false pytest status, and exit 1.
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`

## 2. Documents

- [x] 2.1 Update the `ci-fail-to-pass` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 4938-fail-to-pass-traceback-on-base-timeout`
