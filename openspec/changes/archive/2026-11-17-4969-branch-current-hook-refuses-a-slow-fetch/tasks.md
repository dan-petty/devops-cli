# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for the 24 second limit, the timeout message, the failure
      message and the pre-push budget.
  - Verification: `$ uv run devops ci test tests/git/test_branch_current_hook.py`
- [x] 1.2 Raise the fetch limit and tell a timeout from a fetch failure.
  - Verification: `$ uv run devops ci test tests/git/test_branch_current_hook.py`

## 2. Documents

- [x] 2.1 Update the `pre-push-branch-current` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 4969-branch-current-hook-refuses-a-slow-fetch`
