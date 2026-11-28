# Proposal: #7369

## Why

When `devops ci` runs inside a linked worktree of a clone under `repos/<owner>/<name>`, such as `.data/agent/worktrees/h-1`, `_get_project_root` calls `find_worktree_root`. `find_worktree_root` and `_checks_as_its_own_tree` resolve a worktree whose common git directory belongs to a `repos/` clone back to the outer `devops-cli` workspace, so `devops ci` announces and checks `devops-cli` instead of the nested clone worktree, and `resolve_ci_cache_path` and `resolve_coverage_index_path` key the worktree's files under the outer checkout's hash.

## What Changes

- Add `find_gate_root(start_path)` in `src/devops_cli/core/repo.py` to resolve the nearest enclosing `.git` work tree via `nearest_checkout` (excluding paths inside `.git/`), keeping stale linked worktrees resolvable to themselves, and raise `GitOperationError` with a message naming `start_path` when the directory is outside any git work tree. Keep `find_worktree_root` unchanged for all other callers.
- Add `not_in_work_tree` to `CIMessages` in `src/devops_cli/lang/en/messages.py`.
- Update `_get_project_root` and `all_checks` in `src/devops_cli/commands/ci.py` so the gate resolves the root with `find_gate_root`, stops with exit code 1 and prints the message when outside a git work tree before starting any check, and skips root resolution only when showing subcommand help.
- Update `resolve_ci_cache_path` in `src/devops_cli/ci/cache.py` so cache and coverage-index filenames hash `find_gate_root(root)`.

## Capabilities

### New Capabilities

- `ci-gate-root`: Resolve the quality gate root, stop outside a git work tree, and key the CI cache and coverage index by the gate root.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/core/repo.py`
- `src/devops_cli/commands/ci.py`
- `src/devops_cli/ci/cache.py`
- `src/devops_cli/lang/en/messages.py`
- `tests/commands/test_ci.py`
- `tests/ci/test_ci_cache.py`

## Feasibility

- `src/devops_cli/commands/ci.py:133` calls `find_worktree_root()`.
- `src/devops_cli/core/repo.py:241-253` defines `_checks_as_its_own_tree`, which resolves linked worktrees owned by `repos/` clones back to `workspace_root`.
- `src/devops_cli/git/operations.py:664` already provides `git_show_toplevel(path)` (`git -C <path> rev-parse --show-toplevel`).
- `src/devops_cli/ci/cache.py:89` hashes `str(find_worktree_root(root))`.

## Existing Tool Considered

Considered `git/git` (`https://github.com/git/git`, verdict: `in-use`). Git's linked worktrees place a `.git` file directly inside the worktree root (`.data/agent/worktrees/<id>`), so walking parents with `nearest_checkout` gives the exact work tree without spawning `git` on dry-runs or cache lookups while keeping stale linked worktrees and non-git error stops accurate.
