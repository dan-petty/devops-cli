# Tasks

## 1. A worktree that a run in parallel removed is reported as removed

- [x] Add failing tests: at the `prune_worktrees` level, a worktree whose record and directory a run in parallel removed is reported as `removed` with a failed count of 0; at the `add` level, the same situation reports the worktree in `reclaimed`, sets no `reclaim_error`, exits 0 and prints no warning
  - Verification: `uv run pytest tests/test_repos_worktrees_reclaim.py -q`
- [x] Add `CONST_GIT_NOT_A_WORKTREE_TOKEN`, and make `prune_worktrees` report the worktree as `removed` when git says `is not a working tree`
  - Verification: `uv run pytest tests/test_repos_worktrees_reclaim.py tests/test_repos_worktrees_add.py tests/test_repos_worktrees.py -q`

## 2. Verify

- [x] Run the worktree suites and the architectural invariants
  - Verification: `uv run pytest tests/test_repos_worktrees.py tests/test_repos_worktrees_add.py tests/test_repos_worktrees_reclaim.py tests/test_git_worktree.py tests/test_data_dir_worktrees.py tests/test_architectural_invariants.py -q`
- [x] Lint and type-check the changed files
  - Verification: `uv run ruff check src/devops_cli/config/constants.py src/devops_cli/git/worktree_inventory.py tests/test_repos_worktrees_reclaim.py && uv run mypy --strict src`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2026-10-28-2408-parallel-worktree-remove`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- Not built: a lock or per-worktree file to stop the second removal. The runs already share the repository and the directory, and the message check clears the false warning without new state.
