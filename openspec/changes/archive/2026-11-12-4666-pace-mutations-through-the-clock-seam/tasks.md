# Tasks

## 1. The rate limiter waits through the clock seam (behavior)

- [x] 1.1 Write failing tests: a write waits its one-second interval through the seam, a retry waits its backoff through the seam, and the writes of a command test over `gh_edge` wait through the clock fake. Each test refuses or records the stdlib `time.sleep`.
  - Verification: `$ uv run devops ci test tests/github/test_github_rate_limiter.py`
- [x] 1.2 Call `devops_cli.core.clock.sleep` in `acquire` and `_handle_attempt_backoff` of `src/devops_cli/github/rate_limiter.py`. Make `gh_edge` request `clock`, make `PacedClock` replace the limiter's `clock` name, and make the two tests that recorded the stdlib `time.sleep` read `clock.waits`.
  - Verification: `$ uv run devops ci test tests/github/test_github_rate_limiter.py tests/github/test_service_limits.py tests/commands/test_pr_cmd.py tests/commands/test_gh_cmd.py tests/commands/test_pr_status.py tests/commands/test_pr_title_labels.py tests/commands/test_pr_form_check.py`

## 2. Documents

- [x] 2.1 Say in `docs/TESTING.md` that `gh_edge` sends the rate limiter's waits to the `clock` fixture.
  - Verification: `$ uv run devops ci docs`
