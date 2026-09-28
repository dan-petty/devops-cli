# Task 553: One Data Directory Across Git Worktrees

**Issue**: [#553](https://github.com/dan-petty/devops-cli/issues/553)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/config`, `priority/p1-high`

---

## 1. Description & Objectives

A relative data directory (`.data` by default) resolved against the top of the current git
worktree. Every worktree kept its own history, and removing a worktree deleted it:
- review sessions and profiles;
- benchmarks, corpora and sample validations;
- the analysis and response caches;
- the hallucinations catalog, RAG index, audit log and feedback dataset.

The first full sample validation (#505) was lost that way; its summary survives only in its task
file. The spend ledger was worse: it resolved against whatever directory the command ran in.

### Key Deliverables Completed:

- [x] **`main_worktree_root`** (`core/repo.py`) finds the main worktree from any worktree of a
  repository. A linked worktree's `.git` file names its git directory, whose `commondir` leads to
  the shared git directory inside the main worktree. A `.git` file without `commondir` (a
  submodule's) is not followed, and a directory outside git resolves to itself.
- [x] **`resolve_data_path`** keeps an absolute path as given and puts a relative one under the
  main worktree. Every data output uses it: reviews, benchmarks, the analysis and response
  caches, the hallucinations catalog, the RAG index, the audit log, the feedback dataset,
  samples and the spend ledger. Input datasets checked into the repository still resolve in the
  current worktree.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_data_dir_worktrees.py`, against a real repository with a linked worktree:
    - the main worktree is found from the main worktree, a linked one and a subdirectory;
    - relative data paths are shared, and absolute ones kept;
    - a submodule-style `.git` file and a plain directory keep their own root;
    - a review saved from a linked worktree goes to the main worktree's data directory;
    - the spend ledger resolves there from a subdirectory.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
