# Tasks

## 1. Poll again after a failed read

Reads: `src/devops_cli/github/pr_monitor.py`. Changes: the same file, the message catalog, and `tests/github/test_pr_monitor_retry.py`.

- [x] 1.1 Catch `GitHubOperationError` and count consecutive failures.
- [x] 1.2 Add the warning message.
- [x] 1.3 Add the two tests.
  - Verification: `$ uv run devops ci test tests/github/test_pr_monitor_retry.py` passes
