# Tasks

## 1. Stop on a refused identity

- [x] 1.1 Failing tests: `tests/test_service_limits.py` (identity cases) and the suspended phrase in `tests/test_github_errors.py`. Verify: `uv run devops ci test tests/test_service_limits.py tests/test_github_errors.py`
- [x] 1.2 Add the phrase to the gh-output table, `identity_refused`, the halt of `RoundPause`, and the break in `_execute_due_rows`. Verify: same command.

## 2. Keep requests under a budget

- [x] 2.1 Failing tests for `RequestBudget`, the held rounds and the derived poll interval. Verify: `uv run devops ci test tests/test_service_limits.py`
- [x] 2.2 Add `service.github_requests_per_hour`, `RequestBudget` and `ServiceManager.poll_interval`. Verify: same command.

## 3. Suspend a failing job

- [x] 3.1 Failing tests for `FailureLedger` and `run_due_jobs`. Verify: `uv run devops ci test tests/test_service_limits.py`
- [x] 3.2 Add `FailureLedger` and wire it into the Service's jobs. Verify: `uv run devops ci test tests/test_roadmap_run.py tests/test_server_service.py`

## 4. Documentation

- [x] 4.1 Regenerate the documentation with `uv run devops docs generate --sync-readme`.

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
