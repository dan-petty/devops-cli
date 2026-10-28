# Tasks

## 1. Hold every worker after the last rate limit of a request

- [x] Add a failing test: a secondary limit at each attempt of one worker's request, through the session and through gh, holds the next worker's request for at least 60 s, with each wait moving the clock
  - Verification: `uv run devops ci test tests/test_service_limits.py`
- [x] Hold the identity's requests before the check for a retry left, in the session's `retry_wait` and in `run_gh`'s `_handle_attempt_backoff`, and delete the early return in `handle_rate_limit_error`
  - Verification: `uv run devops ci test tests/test_service_limits.py tests/test_github_rate_limiter.py tests/test_github_session.py`

## 2. Test how `devops serve --service` gives the Service its state directory

- [x] Add a test: the Service that `devops serve --service` starts over a halt record and a budget record is halted and counts the requests of the window; it fails when `serve.py` gives no `state_dir`
  - Verification: `uv run devops ci test tests/test_roadmap_run.py`

## 3. Correct the text that #2474 made wrong

- [x] Say in the rule comment of `RoadmapServiceIdentityRefused` that a halt stays after a restart, write "cannot" in `ServeMessages.state_unreadable` and in the comments and docstrings that #2474 added, and regenerate the documentation
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py` and `uv run devops docs generate --sync-readme`

## 4. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2523-last-rate-limit-holds-every-worker`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
