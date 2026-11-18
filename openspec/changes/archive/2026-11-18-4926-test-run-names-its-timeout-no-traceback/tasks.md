# Tasks

## 1. Behavior

- [x] 1.1 Add a `--timeout` option to `devops test run` and pass it to `run_subprocess`
  - Verification: `$ uv run devops ci test tests/commands/test_test_runner.py`
- [x] 1.2 Catch `subprocess.TimeoutExpired` in `run_test_cmd` and raise a `DevOpsCLIError` that names the effective seconds and the `--timeout` option
  - Verification: `$ uv run devops ci test tests/commands/test_test_runner.py`
- [x] 1.3 Write the tests for the timeout line, the option value, the effective value and the non-timeout path
  - Verification: `$ uv run devops ci test tests/commands/test_test_runner.py`

## 2. Documents

- [x] 2.1 Add the `test-run-timeout` capability
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
