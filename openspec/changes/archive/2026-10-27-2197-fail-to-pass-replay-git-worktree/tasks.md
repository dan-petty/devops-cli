# Tasks

## 1. Replay in a git worktree

- [x] Add the failing tests for `git ls-files` in the replay and for no leftover worktree
  - Verification: `uv run devops ci test tests/test_fail_to_pass.py`
- [x] Replace the `git archive` extraction of the base tree with a detached worktree that is always removed
  - Verification: `uv run devops ci test tests/test_fail_to_pass.py`
- [x] Run full CI quality checks
  - Verification: `uv run devops ci`
