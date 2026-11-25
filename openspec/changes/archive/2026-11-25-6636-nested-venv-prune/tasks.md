# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests in `tests/git/test_repos_worktrees_reclaim_scope.py` for nested `.venv`, data beside nested `.venv`, nested `build`, and `prune` preview
  - Verification: `$ uv run pytest tests/git/test_repos_worktrees_reclaim_scope.py`
- [x] 1.2 Update `CONST_WORKTREE_REGENERABLE_PATHSPECS` in `src/devops_cli/config/constants.py` to exclude `:(exclude,glob)**/.venv/**`
  - Verification: `$ uv run pytest tests/git/`

## 2. Documents

- [x] 2.1 Update `openspec/specs/repos-worktrees-prune/spec.md` via OpenSpec archive and pass CI checks
  - Verification: `$ uv run devops ci --check --no-cache --only lint,format,typecheck,test-tree,docs,openspec`
