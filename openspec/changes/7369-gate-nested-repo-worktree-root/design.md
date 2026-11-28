# Design

## Decisions

- **Resolve via `nearest_checkout` in `find_gate_root`**: `find_gate_root(start_path)` resolves `current` and calls `nearest_checkout(current)` to find the nearest enclosing directory containing `.git` (refusing paths inside `.git/` itself). This resolves linked worktrees of clones under `repos/` (whose `.git` entry sits directly in `.data/agent/worktrees/<id>`), preserves stale linked worktree warnings, and spawns zero `git` subprocesses during `--dry-run`, cache lookups, or process-faked tests.
- **Keep `find_worktree_root` unchanged**: Other commands and `tests/commands/test_repos.py` depend on `find_worktree_root` resolving `repos/` clone worktrees to the enclosing workspace. Only the quality gate and its cache/coverage index switch to `find_gate_root`.
- **Stop cleanly outside a git work tree**: When `nearest_checkout` finds no enclosing `.git` work tree, `find_gate_root` raises `GitOperationError` with `MESSAGES.ci.not_in_work_tree` naming the resolved directory, and `_get_project_root` prints the message and exits 1 before any check runs (skipping root resolution when displaying subcommand `--help`).
- **Key CI cache and coverage index by `find_gate_root(root)`**: `resolve_ci_cache_path` hashes `str(find_gate_root(root))`, giving nested clone worktrees distinct cache and coverage index files from the outer checkout while `resolve_coverage_index_path` reuses the suffix from `resolve_ci_cache_path`.

## Rejected alternatives

- **Calling `git_show_toplevel` (`git rev-parse --show-toplevel`) on every root lookup**: Starts a `git` subprocess during `--dry-run`, breaks process-fake dry-run and audit assertions, and triggers `ci_head`'s `rev-parse` test double.
- **Changing `find_worktree_root` directly**: Breaks workspace-level commands and existing assertions in `tests/commands/test_repos.py`.
- **Falling back to `pyproject.toml` or current working directory outside a git repo**: Checks a non-worktree directory or wrong parent repository and violates the stop-outside-work-tree requirement.
- **Adding a `--root` option to every gate command**: Leaves the default broken for nested clone worktrees.
