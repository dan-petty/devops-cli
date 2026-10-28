# Tasks

## 1. Read a suspended installation and a header-less 403 to a write as a refused identity

- [x] Add failing tests: the gh-output table reads both suspended-installation texts as `GitHubUnauthenticatedError`; a 403 to a write with no `x-ratelimit-*` header is `GitHubUnauthenticatedError` and one with them is not; the Service halts on each
  - Verification: `uv run devops ci test tests/test_github_errors.py tests/test_service_limits.py`
- [x] Add the two phrases to `CONST_GITHUB_UNAUTHENTICATED_PATTERNS` and the refused-write row to `_HTTP_CLASSES`
  - Verification: `uv run devops ci test tests/test_github_errors.py tests/test_service_limits.py`

## 2. Hold every worker's requests during a rate-limit wait

- [x] Add a failing test: after one worker's request gets a 403 with `retry-after: 60`, the next worker's request waits until the 60 s end
  - Verification: `uv run devops ci test tests/test_service_limits.py`
- [x] Add `GitHubRateLimiter.hold_requests`, schedule each request after the hold, and call it from the session's `retry_wait` and from `run_gh`'s backoff
  - Verification: `uv run devops ci test tests/test_service_limits.py tests/test_github_rate_limiter.py tests/test_github_session.py`

## 3. Keep the halt, the budget window and the ledger across a restart

- [x] Add failing tests: a new Service over the same directory finds the halt, counts the refusal once, and finds the 60 requests of the window and the suspended job; a record that cannot be read stops the start
  - Verification: `uv run devops ci test tests/test_service_limits.py`
- [x] Keep the records in `service_state_dir()`, read them back at start, count a kept halt once, delete `SERVICE_JOBS` and `SERVICE_FAILURES`, and build the lane jobs with `service_jobs(state_dir)`
  - Verification: `uv run devops ci test tests/test_service_limits.py tests/test_roadmap_run.py tests/test_server_service.py`
- [x] Say in `k8s/README.md` where the records are and how to clear a halt, say in the description of `RoadmapServiceIdentityRefused`, its promtool test and its README row that a restart keeps the halt, and regenerate the documentation
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py` and `uv run devops docs generate --sync-readme`

## 4. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2474-service-state-survives-restart`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
