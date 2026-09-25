# Task 612: Worktree Gate Resolution Keeps repos/ Clones on the Workspace and Checks Stale Worktrees

**Issue**: [#612](https://github.com/dan-petty/devops-cli/issues/612)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

#585 fixed #582 for nested worktrees, but its `find_worktree_root` stopped at the first
directory with its own `.git`. That broke two things #582 said must stay as they were, and it
left stale worktrees on the old behaviour:
- **Clones under `repos/`:** the gate, and `main_worktree_root` with it, resolved a clone
  under `repos/` and each worktree of it to the clone. Its reviews, caches and catalogue went
  into `repos/<org>/<repo>/.data`, inside the clone's own working tree, instead of the
  workspace's shared data directory (#553).
- **Stale worktrees:** a nested worktree whose `.git` file named a missing git directory,
  because it was pruned or its main checkout moved, still resolved to the enclosing checkout,
  so the gate silently checked the main checkout again.
- **Invisible root:** the gate named its root only in the concurrent run's header. A cached
  verdict, and a single check such as `devops ci test` run by the pre-commit hook, never showed
  which tree they judged.
- **Import-time root:** `commands/ci.py` kept an import-time `_ROOT`, so a long-lived process
  that imported it from another directory cleaned the wrong tree's coverage files.

### Key Deliverables Completed:

- [x] **`find_worktree_root`** (`src/devops_cli/core/repo.py`) stops at the nearest linked
  worktree, live or stale, of the workspace's own repository, or of a repository outside the
  workspace. Otherwise it keeps the top-level workspace root, so the main checkout, clones
  under `repos/`, their worktrees and submodules resolve as they did before #585.
  - Relative-path worktrees, worktrees of a bare repository, and `.git` files that are
    unreadable or not UTF-8 (read with `surrogateescape`) are handled.
  - `is_stale_linked_worktree` reports a worktree whose git directory is missing.
- [x] **`main_worktree_root`** starts from the top-level root again, so shared data for a clone
  under `repos/` and its worktrees stays in the workspace's data directory, and every nested,
  outside, relative-path or pruned worktree of the checkout shares the main worktree's.
- [x] **Gate root shown and resolved when needed** (`src/devops_cli/commands/ci.py`):
  - the gate names its root before the cache lookup, so a cached verdict shows it too, and
    every single check (`devops ci lint`, `devops ci test`, ...) names it as well, except for
    `--help`;
  - from a stale worktree it warns, with the fix for each cause: `git worktree repair <path>`
    when the main checkout moved, or move the worktree aside and re-create it with
    `git worktree add` when it was pruned;
  - the import-time `_ROOT` is gone; the root, including the coverage clean-up's, is resolved
    on each call. Messages live in `lang/en/messages.py`.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_repos.py`, against real repositories: nested, outside, relative-path, pruned
    and moved-checkout worktrees check themselves; the main checkout, a clone under `repos/`
    and its worktrees, a submodule (also with a missing git directory) resolve to the
    workspace; bare-repository worktrees, a file path, undecodable and non-UTF-8 `.git` files.
  - `tests/test_data_dir_worktrees.py`: nested, relative-path and pruned worktrees share the
    main worktree's data; a clone under `repos/` and its worktree share the workspace's.
  - `tests/test_ci.py`: a real `ruff` run in which a lint error only the worktree has fails the
    single check and one only the main checkout has does not; a cached verdict names the
    worktree; the stale-worktree warning's repair command restores a worktree whose checkout
    moved; staged sources select the worktree's tests; coverage clean-up follows the directory
    the gate runs in; `--help` does not name the root.
  - `test_release.py`, `test_test_runner.py`, `test_uv.py` and `test_scan_complexity.py`
    check each verifying command from a nested worktree.
  - An acceptance probe over eleven real layouts matches the required gate and data roots
    exactly.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
