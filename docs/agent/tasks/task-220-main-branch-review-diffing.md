# Task 220: Support Main Branch Diffing and Base Resolution in Review Branch

**Issue**: [#220](https://github.com/dan-petty/devops-cli/issues/220)
**Status**: Done
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/ai`

---

## 1. Description & Objectives

When running `devops ai review branch` on the `main` branch, or when executing `devops ai review branch main` from another branch (e.g. `release/v0.2.19`), the CLI resolves `branch_name="main"` and `effective_base="main"`. This causes `git diff main...main` to run, producing zero differences and immediately exiting with `No differences found between branches.`

#### Key Deliverables:
1. **Branch & Base Target Resolution ([`src/devops_cli/ai/review/runner.py`](file:///workspaces/devops-cli/src/devops_cli/ai/review/runner.py))**:
   - Added `_resolve_branch_targets`, `_get_current_git_branch`, `_has_uncommitted_working_tree_changes`, and `_resolve_main_branch_fallback_base`.
   - When `target_branch == effective_base` and current active branch differs (e.g. executing `devops ai review branch main` while on `release/v0.2.19`), automatically interprets the argument as the target base and reviews the current active branch against it.
   - When on `main` branch (or matching base) and working tree has uncommitted changes, diffs against `HEAD`.
   - When on `main` branch with a clean working tree, resolves fallback base using latest git release tag or parent commit (`main~1`).
   - Decomposed `_detect_base_branch` by extracting `_detect_remote_default_branch` to maintain cyclomatic complexity $\le 10$ and nesting $\le 2$.
2. **Submodule-Aligned Unit Tests ([`tests/test_review_runner.py`](file:///workspaces/devops-cli/tests/test_review_runner.py))**:
   - Added unit tests for `_get_current_git_branch`, `_has_uncommitted_working_tree_changes`, `_resolve_main_branch_fallback_base`, `_resolve_branch_targets`, and `_prepare_branch_content` covering all resolution branches.
   - 100% passing across all unit tests and full static type checking (`mypy`).
