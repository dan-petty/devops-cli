# Task 700: Worktree Inventory & Safe Orphan Reclamation (`devops repos worktrees`)

**Issue**: [#700](https://github.com/dan-petty/devops-cli/issues/700)
**Status**: Done
**Milestone**: `v0.2.34`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`
**Feasibility**: Verified with `git worktree list --porcelain -z` and `git for-each-ref --contains` across local repository worktrees.

---

## 1. Description & Objectives

External harnesses and multi-agent workflows leave behind worktree checkouts that accumulate over time. While git itself reports `locked` and `prunable` states, it cannot determine whether an orphan checkout holds unmerged commits or dirty modifications.

This deliverable implements the `devops repos worktrees` command group with:
1. `devops repos worktrees status`: lists every worktree in the repository with per-entry commits ahead of main, dirty-path count, whether any other local or remote ref contains the tip, and git's `locked` and `prunable` status.
2. `devops repos worktrees status --json`: emits a typed JSON array containing `ahead` (int), `dirty` (int), `contained` (bool), `locked` (bool), and `prunable` (bool).
3. `devops repos worktrees prune`: dry-run preview by default; without `--force`, removes only clean and contained entries, refusing dirty, unmerged, locked, or main worktrees.
4. `devops repos worktrees prune --force`: removes worktrees regardless of clean or unmerged status, cleaning up metadata with `git worktree prune`.
5. NUL-separated parsing via `git worktree list --porcelain -z` per the #1440 convention, cleanly preserving paths with newline bytes.

#### Key Deliverables:
- [x] NUL-separated porcelain worktree list parser (`parse_worktree_porcelain_z` in `src/devops_cli/git/worktree_inventory.py`).
- [x] Ahead-of-main calculation (`count_commits_ahead_of_main`), dirty path counting (`count_dirty_paths`), and other-ref containment verification (`is_tip_contained_in_other_ref`).
- [x] Safe prune evaluator (`evaluate_prune_candidates` and `prune_worktrees`), refusing unmerged/dirty checkouts without `--force` and invoking `git worktree prune` on completion.
- [x] CLI commands `devops repos worktrees status` and `devops repos worktrees prune` with `--json`, `--force`, `--dry-run`, and `--repo-dir` flags in `src/devops_cli/commands/repos.py`.
- [x] Unit and integration test suite in `tests/test_repos_worktrees.py` covering all 8 acceptance criteria.
- [x] Maintained cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
