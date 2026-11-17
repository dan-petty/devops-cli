# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for a link that appears on the second read, a link that never
      appears, and the issue number that `set_delivered_status` returns.
  - Verification: `$ uv run devops ci test tests/commands/test_pr_status.py`
- [x] 1.2 Retry the closing-issue read for a bounded time and warn when no issue links.
  - Verification: `$ uv run devops ci test tests/commands/test_pr_status.py`

## 2. Documents

- [x] 2.1 Update the `roadmap-item-labels` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 5112-pr-create-sets-in-progress-after-github-links`
