# Task 323: Git Low-Level Plumbing Optimization, PathSpec In-Memory Tree Caching & Parallel Worktree Research

**Issue**: [#323](https://github.com/dan-petty/devops-cli/issues/323)
**PR**: [#373](https://github.com/dan-petty/devops-cli/pull/373)
**Status**: In Review
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`is_ignored_by_git` loaded only the repository root's `.gitignore` and, on a miss, spawned
`git check-ignore` for the file. A miss is the *common* case — most files in a repository
are not ignored — so the fast path was the rare one and a process was spawned per file.
Measured over this repository's own sources before any change:

```
300 tracked files:   11.84s  (39.5 ms/file)
200 gitignored files: 0.05s  ( 0.3 ms/file)
```

The asymmetry is the whole defect: a file the root `.gitignore` matched was resolved in
memory, and every other file paid for a subprocess.

Reading only the root file was also incorrect. Git consults a `.gitignore` in every
directory between the repository root and the file, plus `.git/info/exclude`, with deeper
files overriding shallower ones and `!` re-including. A nested rule was invisible to the
in-memory path and could only ever be resolved by the subprocess — and this repository
contains 187 `.gitignore` files.

### Key Deliverables Completed:

- [x] **In-Memory Ignore Evaluation (`src/devops_cli/core/gitignore.py`)**:
  - Full git semantics via `pathspec`: nested `.gitignore` files, `.git/info/exclude`,
    negation, anchored and unanchored patterns, `**`, and directory-only patterns.
  - A path inside an ignored directory is ignored regardless of any rule that would
    re-include it. Git does not descend into an excluded directory, so a negation there can
    never take effect; evaluating a file's own rules without checking its ancestors reports
    it as tracked when git would not.
  - Ignore files are applied root-downwards, so precedence matches git's.
- [x] **No Subprocess On Any Path**: the `git check-ignore` fallback is gone.
- [x] **Cost Driven Into The Filesystem, Then Out Of It**: the first correct implementation
  was still slow (21.1 ms/file). Profiling showed 2404 `stat` and 2396 `lstat` calls for
  150 files — four path resolutions and ten ignore-file stats each — and an $O(d^2)$
  ancestor walk. It evaluated the rules correctly and spent all its time in the filesystem.
  Restructured into a single linear descent, with paths taken as given rather than resolved
  (which also matches git) and compiled ignore files revalidated on an interval.
- [x] **Optional `is_dir`**: directory-only patterns need to know whether a path is a
  directory, and on a slow filesystem that one `stat` is most of the remaining cost. A
  caller that has just listed a directory already knows, so it can now say.
- [x] **Centralized Constants**: ignore filename, local exclude path, pattern style,
  revalidation interval.
- [x] **Automated Tests & Quality Gates**:
  - 22 tests in `tests/test_gitignore_evaluation.py`, most of which assert agreement with
    **real `git check-ignore`** against a temporary repository rather than with an
    assumption about git's behaviour.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

| Case | Before | After | After, with `is_dir` supplied |
| --- | --- | --- | --- |
| Tracked source files | 39.5 ms/file | 1.9 ms/file | **0.73 ms/file** |
| Ignored files (`.venv`) | 0.3 ms/file | 0.2 ms/file | 0.2 ms/file |

A **54× improvement** on the case that dominates a repository walk, and correctness
cross-checked against git over 260 real paths spanning tracked sources, `.venv`, `.data`,
`k8s`, `.github` and build caches: **zero mismatches**.

## Design Constraint: Correctness Before Speed, Checked Against Git Itself

An ignore evaluator that is fast and subtly wrong silently changes what gets indexed,
reviewed and shipped — including, potentially, reading files the operator expects to be
excluded. Every semantic test therefore asks `git check-ignore` for the answer instead of
encoding an assumption about what git does, and the implementation was cross-checked
against the real repository before any optimization was attempted. The optimization work
happened only after the correctness result was established, and the cross-check was re-run
after each change.

## Freshness Trade-off, Stated Explicitly

Compiled ignore files are revalidated at most once per `DEFAULT_GITIGNORE_REVALIDATE_SECONDS`
(2.0s) rather than stat-ed on every check. This is a deliberate trade, measured:

| Revalidation | Cost |
| --- | --- |
| Every call | 4.97 ms/file |
| Interval (2.0s) | 0.40 ms/file |

Over a 10,000 file index that is 50 seconds against 4. The cost is that a `.gitignore`
edited *during* a run is not visible for up to two seconds; `reset_indexes()` makes it
immediate for callers that need it. Two existing tests wrote a `.gitignore` and re-checked
in the same breath, and now reset explicitly — the contract is a documented window, not an
accident.

## Scope Note

**Parallel multi-repository fetch and `pygit2` bindings were not implemented.** The
measured cost in this area was ignore evaluation, not object access, and replacing GitPython
with `pygit2` is a dependency and a rewrite justified by a benchmark nobody has taken.
Parallel fetch is a real opportunity but it is network-bound work whose failure modes
(partial fetches, interleaved credential prompts, rate limiting) deserve their own task
rather than riding along with a correctness fix. **Shadow worktree provisioning** was left
out for the same reason: nothing in the codebase consumes a worktree today, so it would
ship an unexercised path.
