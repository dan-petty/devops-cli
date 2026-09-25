# Task 582: Gate Checks the Worktree It Runs In, Not the Main Checkout (`devops ci`)

**Issue**: [#582](https://github.com/dan-petty/devops-cli/issues/582)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

`devops ci` previously resolved its project root via `find_top_level_repo_root()` (`src/devops_cli/core/repo.py`), which traversed up the directory tree and kept the top-most ancestor holding `.git` or `pyproject.toml`.

When running from a linked worktree nested inside the main checkout (e.g. `.claude/worktrees/<name>/`), `find_top_level_repo_root()` resolved to the parent checkout rather than the active worktree. Consequently, pre-push gates in worktrees failed on dirty or uncommitted files in the main checkout, while broken branches in worktrees falsely passed whenever the main checkout was clean. The same applied to `devops test`, `devops uv`, `devops release`, and `devops scan complexity`. Furthermore, `main_worktree_root()` started from `find_top_level_repo_root()`, preventing it from recognizing a worktree nested inside the checkout.

### Key Deliverables Completed:

- [x] **`find_worktree_root`** (`src/devops_cli/core/repo.py`):
  - Adds a dedicated resolver that stops at the nearest enclosing worktree: the first directory whose `.git` is a `gitdir:` file with a `commondir`, or a `.git` directory.
  - Falls back to `find_repo_root(current)` if no git worktree is found.
  - Submodule `.git` files without a `commondir` are not treated as worktrees and continue resolving to the enclosing repository as before.
- [x] **Verification Command Integration**:
  - `devops ci` (`src/devops_cli/commands/ci.py`): `_get_project_root()` uses `find_worktree_root()`.
  - `devops ci` header prints the resolved root (`Executing CI quality gates concurrently in <root>...`) for transparency.
  - `devops test` (`src/devops_cli/commands/test_cmd.py`): uses `find_worktree_root()`.
  - `devops uv` (`src/devops_cli/commands/uv.py`): uses `find_worktree_root()`.
  - `devops release` (`src/devops_cli/commands/release.py`): uses `find_worktree_root()`.
  - `devops scan complexity` (`src/devops_cli/security/complexity.py`): uses `find_worktree_root()`.
- [x] **Nested Worktree Shared Data Resolution**:
  - `main_worktree_root()` (`src/devops_cli/core/repo.py`): starts from `find_worktree_root()`, allowing both external and nested linked worktrees to follow `commondir` back to the main repository for `.data/` persistence (#553).
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_repos.py`: unit tests verifying `find_worktree_root` correctly resolves main repos, nested linked worktrees, submodules, and standalone projects.
  - `tests/test_data_dir_worktrees.py`: verifies nested linked worktree resolves `main_worktree_root` and `resolve_data_path` to the main repository.
  - `tests/test_ci.py`: integration test with a real nested `git worktree add` ensuring that a lint error present only in the worktree fails the gate, while an error present only in the main checkout does not.
  - 100% passing status across the Gated CI Quality Gate suite (`uv run devops ci`).
