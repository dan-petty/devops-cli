# Tasks

## 1. Catch FileNotFoundError when measuring directory size

- [x] 1.1 Add failing tests in `tests/test_repos_worktrees.py` verifying that `directory_size` handles deleted files gracefully, verified to fail on base with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Implement `_file_size` helper in `src/devops_cli/git/worktree_inventory.py` to catch `FileNotFoundError` and return 0 bytes, verified with `uv run devops ci test tests/test_repos_worktrees.py tests/test_repos_worktrees_reclaim.py`
- [x] 1.3 Validate full test suite and quality gates, then archive change with `uv run devops openspec archive 2412-worktrees-add-filenotfounderror`
