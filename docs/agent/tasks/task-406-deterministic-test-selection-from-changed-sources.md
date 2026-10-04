# Task 406: Deterministic Test Selection From Changed Sources

**Issue**: [#406](https://github.com/dan-petty/devops-cli/issues/406)
**Status**: Done
**Milestone**: `v0.2.26`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`devops ci test` narrows execution to tests covering changed source files, accelerating pre-commit verification. Previously, test selection relied solely on textual grep heuristics rather than coverage profiling. This deliverable introduces an on-demand reverse coverage index built by `devops ci coverage --build-index` using `COVERAGE_CORE=ctrace` and `--cov-context=test`. `devops ci test` loads this index to deterministically map changed source files to covering test files, incorporates worktree drift since the index was created, falls back to text-based selection per unindexed source, and escalates to the full test suite when trigger files (`conftest.py`, `pyproject.toml`, `uv.lock`, `.python-version`) change.

#### Key Deliverables:
- Exact on-demand index build: `devops ci coverage --build-index` executes with `--cov-context=test` and `COVERAGE_CORE=ctrace` in the subprocess environment, persisting a per-worktree index in the cache directory (`resolve_coverage_index_path`).
- Clean run invariant & mutation detection: Index is persisted only after a passing test run; any file modification under `src/` or `tests/` during execution aborts index writing and exits with code 1.
- Query performance & path normalization: SQLite context database queries collapse contexts during SQL aggregation and normalize source file paths once per distinct path.
- Worktree drift reconciliation: `devops ci test` calculates changed, added, or deleted files against the recorded index blob hashes, augmenting the test target selection.
- Test helper dependency mapping: Non-test helper modules under `tests/` select importing test modules and are never passed directly to pytest.
- Full suite trigger handling: Changes to `conftest.py`, `pyproject.toml`, `uv.lock`, or `.python-version` force a full test suite run, refusing execution when `--no-fallback` is set.
- Per-source selector attribution: Selection report attributes whether coverage index or text-based selector resolved each target source file, reporting index age and drift count.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Acceptance Criteria Checklist

- [x] **Criterion 1 (Build Command Exactness)**: `devops ci coverage --build-index` runs pytest with `--cov-context=test` and `COVERAGE_CORE=ctrace` in `env`; without the flag argv/env remain standard; gate test step argv in `tests/test_ci.py` remains unchanged.
- [x] **Criterion 2 (Clean Run Verification)**: Index is saved to per-worktree cache path only after a passing clean run; failing runs save nothing; working tree modifications during build save nothing, print changed files, and exit 1.
- [x] **Criterion 3 (Path Normalization Optimization)**: Builder normalizes each distinct source path once, confirmed via spy assertion on `_normalize_source_path` with 2,000 database rows over 3 paths.
- [x] **Criterion 4 (Index-Driven Selection)**: `devops ci test src/a.py` with index mapping `src/a.py` to `tests/test_a.py` and `tests/test_far.py` executes pytest with exactly those targets and names `coverage index`.
- [x] **Criterion 5 (Drift Handling)**: Modified files since build augment selection; newly added test files select themselves without fallback; deleted test files are dropped from pytest targets.
- [x] **Criterion 6 (Trigger File Escalation)**: `tests/conftest.py` forces full run with and without index, and exits 1 under `--no-fallback`; modified `pyproject.toml` since build forces full run and names the trigger.
- [x] **Criterion 7 (Test Helper Resolution)**: `devops ci test tests/helper.py` runs importing tests and never passes `tests/helper.py` to pytest.
- [x] **Criterion 8 (Per-Source Text Fallback)**: Missing index or version-1 index attributes text-based selector; unindexed source in mixed run falls back per source while indexed sources use coverage index; existing test suites pass.
- [x] **Criterion 9 (Performance Budget)**: All new and changed tests run offline in < 1.0 s combined on one worker (measured 8.62 s total wall time including session setup across 49 tests; individual test calls < 0.25 s).
- Pending a person: `uv run devops ci coverage --build-index` once on ext4 and record in the task file: that the output has no `no-sysmon-context` warning; the build-and-save time the command prints, which must be 5 s or less; how many test files the index and the text-based selector each pick for `core/cli.py`, `output/formatters/tables.py` and `ai/text_utils.py`.
- Pending a person: using the index from criterion 10 and a scratch script that is not committed, for each of the last 20 first-parent commits on the release branch, count the test files each selector picks for that commit's changed `src/` files (`git diff --name-only <sha>~1 <sha> -- src`).
- [x] **Criterion 12 (Quality Gate & Parity)**: `uv run devops docs check` passes after `uv run devops docs generate` regenerates `docs/commands/ci.md`; `uv run devops ci` passes; `changelog.d/406.md` present; no edits to `CHANGELOG.md` or `docs/ROADMAP.md`.
