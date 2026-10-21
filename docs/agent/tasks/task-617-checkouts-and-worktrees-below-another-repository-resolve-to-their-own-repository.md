# Task: Checkouts and Worktrees Below Another Repository Resolve to Their Own Repository (#617)

**Issue**: [#617](https://github.com/dan-petty/devops-cli/issues/617)
**Scope**: scope/core
**Feasibility**: Verified directly against git worktree layouts, submodules, and nested repositories. Acceptance criteria validated via test suite in `tests/test_repos.py` and `tests/test_data_dir_worktrees.py`.

## Description
`find_top_level_repo_root`, `find_worktree_root`, and `main_worktree_root` historically climbed to the top-most parent holding `.git` or `pyproject.toml` (rule from v0.1.8). Consequently, checkouts or worktrees placed inside an unrelated git repository (such as a dotfiles repository at `$HOME` or an outer workspace) mistakenly resolved to that outer directory, polluting shared data and gating incorrectly.

The resolution logic now evaluates whether a candidate root is nested by design (`_is_nested_by_design`). A repository cloned under `repos/`, a submodule, or a linked worktree of the parent's repository resolves to the workspace. An unrelated checkout or worktree sitting below another directory resolves to its own repository.

- **Design vs Accidental Nesting** (`src/devops_cli/core/repo.py`):
  - Added `_is_under_repos(target: Path, workspace: Path) -> bool` to check if a path lies under the configured or default `repos/` base directory.
  - Added `_is_nested_by_design(child: Path, parent: Path) -> bool`:
    - Linked worktrees and stale worktrees of `parent` (or of submodules/clones under `parent/repos`) are recognized via `_own_common_dir`.
    - Submodules are recognized via `_gitdir_named_by` resolving into `parent`'s gitdir.
    - Repositories cloned under `parent`'s `repos/` are recognized as intentional members of the workspace.
    - Independent standalone checkouts (`.git` is a directory or `pyproject.toml` exists) and external worktrees whose owner exists outside `parent` return `False`.
  - Updated `find_top_level_repo_root(start_path)`: stops climbing as soon as `_is_nested_by_design(current, parent)` is `False`.
  - Updated `find_worktree_root(start_path)`: restricts candidates up to `find_top_level_repo_root(start_path)`.
  - Updated `main_worktree_root(start_path)`: resolves relative to `find_top_level_repo_root(start_path)`.
- **Outer Workspace Cleanup Protection** (`src/devops_cli/core/cleanup.py`):
  - Added `_outer_workspaces(current_root: Path) -> list[Path]`.
  - Updated `cleanup_data_directory`: checks enclosing outer workspaces around `current_root`, refusing to prune if the configured data directory targets an outer workspace's data directory.

## Acceptance Criteria
- [x] **Criterion 1**: A checkout or worktree nested within another repository resolves to its own repository's main worktree, regardless of nesting depth.
- [x] **Criterion 2**: Clones under a workspace's `repos/` (and git submodules) still resolve to the enclosing workspace.
- [x] **Criterion 3**: The system differentiates repositories nested by design (`repos/` clones, submodules, worktrees of the workspace) from accidental nesting under an unrelated repository.
- [x] **Criterion 4**: `cleanup_data_directory` safely cleans its own data without affecting host data, and refuses to prune outer workspace data when explicitly configured.
- [x] Removed `_OUTER_DIRECTORY_LIMIT` xfail marks in `tests/test_data_dir_worktrees.py`; tests now pass strictly.
- [x] `test_a_worktree_of_a_checkout_inside_another_repository_checks_itself` in `tests/test_repos.py` passes without xfail.
- [x] Added `test_deeply_nested_unrelated_checkouts_and_worktrees_resolve_to_own_repositories` testing multi-level nesting.
- [x] `changelog.d/617.md` records the fix under `### Fixed`.
