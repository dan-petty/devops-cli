# Task: Review Scans a Worktree of the Reviewed Revision (#1047)

**Issue**: [#1047](https://github.com/dan-petty/devops-cli/issues/1047)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/review

## Description
Prior to this change, reviews of branches and pull requests scanned files directly in the working checkout. Uncommitted local edits, dirty worktrees, or checkout state contaminated the review, yielding false findings or inaccurate symbol deltas that did not reflect the reviewed commit. Deleted files in a change set were handed to static analyzers which failed or complained about missing paths. Furthermore, there was no granular coverage matrix reporting which files each tool actually scanned, skipped, or failed on.

Reviews now scan an isolated, detached git worktree created under the user data root (`~/.local/share/devops-cli/worktrees`), guaranteeing full isolation from uncommitted checkout changes. The worktree is automatically cleaned up on exit. Change set parsing uses `git diff --name-status -M` to ensure deleted files are excluded from scanner targets while renames track head target paths and preserve old paths. Pre-analysis reuses cached metadata when the content hash matches the commit blob, bypassing mtime. Path classes (`src`, `test`, `fixture`, `iac`, `docs`) are loaded from `.devops/review.toml`, scoping test fixtures to secret scanning only. A per-(tool, file) coverage matrix is persisted to `profile.json` and rendered in `review.md`. Gitleaks regex fallback is eliminated in favor of deterministic binary execution reporting `not installed` when missing.

## Key Changes
- **Isolated Detached Worktrees** (`src/devops_cli/git/worktree.py`):
  - `get_user_worktrees_dir()` resolves `worktrees/` under user data root (or `DEVOPS_CLI_USER_DATA_ROOT` environment override).
  - `add_detached_worktree()` and `remove_worktree()` manage creation and pruning of detached git worktrees.
  - `fetch_pr_head()` fetches `refs/pull/<N>/head` from remote.
  - `review_worktrees_context()` context manager provisions detached worktrees for target and base revisions and ensures removal in a `finally` block.
- **Review Command Integration** (`src/devops_cli/commands/review.py`):
  - `branch()` enters `review_worktrees_context()` when target commit is resolved, running static scans and pre-analysis against the isolated worktree. If uncommitted work is reviewed (`base_revision.read_head is None`), it scans in place and prints "Scanning in place (uncommitted work)...".
  - `pr()` attempts `fetch_pr_head()`. If available, it executes in a detached worktree with `partial_context=False`. If unavailable, it prints a warning, uses materialized head files, and sets `partial_context=True`.
  - Single-file path review resolves repository root using `git_show_toplevel` (`git rev-parse --show-toplevel`).
- **Change Set & Rename Handling** (`src/devops_cli/git/operations.py`, `src/devops_cli/ai/review/chunker.py`, `src/devops_cli/ai/review/runner.py`):
  - `list_changed_files()` parses `git diff --name-status -z --find-renames <base>...<head>`.
  - `chunker.py:_extract_header_filenames()` extracts the head target filename from `b/<path>` for renames.
  - `runner.py:_execute_review_workflow()` filters out `deleted` change entries so deleted files are never passed to static analyzers or orchestrator targets.
- **Pre-Analysis Cache Reuse** (`src/devops_cli/ai/review/pipeline.py`):
  - `_try_reuse_cached_analysis_meta()` reuses cached analysis metadata when the file's SHA-256 hash matches `old_meta.content_hash`, bypassing mtime checks for detached worktrees.
- **Declarative Path Classes** (`src/devops_cli/ai/review/path_classes.py`, `.devops/review.toml`, `src/devops_cli/config/constants.py`):
  - `.devops/review.toml` defines default pattern classes (`src`, `test`, `fixture`, `iac`, `docs`).
  - `load_path_classes()`, `classify_path()`, and `is_fixture_path()` classify paths and route test fixtures and golden sets to secret scanning only (Gitleaks).
  - General analyzers (Bandit, Kube-linter, Pluto, Semgrep, Trivy) skip fixture paths with status `skipped(fixture)`.
- **Tool Coverage Matrix** (`src/devops_cli/ai/review/profile.py`, `src/devops_cli/ai/review/pipeline.py`):
  - `ReviewProfile` records `coverage: dict[str, dict[str, str]]` and `partial_context: bool`.
  - `_compute_coverage_matrix()` resolves outcomes per `(tool, file)`: `scanned`, `skipped(fixture)`, `skipped(not python)`, `skipped(not manifest)`, `skipped(not container or lockfile)`, `failed(reason)`, `timed out after N s`, `not installed`, `canary failed`.
  - `_build_coverage_section()` appends the markdown table under `## Coverage` in `review.md`.
- **Gitleaks Cleanup** (`src/devops_cli/security/gitleaks.py`):
  - Deleted `_FALLBACK_SECRET_PATTERNS` and `fallback_scan()`.
  - Missing Gitleaks binary reports outcome status `not installed`.

## Acceptance Criteria
- [x] **Worktree isolation**: In a git repo with base commit, branch commit changing `app.py`, and uncommitted working tree edit adding `extra()`, branch review metadata for `app.py` has commit `content_hash` and does not contain `extra` in `key_symbols`.
- [x] **Deleted files excluded**: Deleted files in a change set are marked `deleted` and excluded from `all_files`, never passed to static analyzers.
- [x] **Rename tracking**: Renamed files keep the old path in `old_path` and track the target path at head for analysis.
- [x] **Pre-analysis cache reuse**: Pre-analysis reuses cached metadata when content hash matches commit blob even if mtime is newer.
- [x] **PR head fetching**: PR heads are fetched from `refs/pull/N/head`; if unavailable, marked with `partial_context=True` and a clear console warning.
- [x] **Path classes**: Path classes loaded from `.devops/review.toml`; fixtures and golden sets are scanned by Gitleaks only.
- [x] **Coverage matrix**: Coverage matrix per `(tool, file)` recorded in `profile.json` and rendered in `review.md` under `## Coverage`.
- [x] **Gitleaks fallback removed**: Missing binary yields status `not installed` without regex fallback.
- [x] **Architectural invariants**: Nesting depth $\le 5$ and complexity $\le 10$ across all modules.
- Pending a person: `uv run devops ci` on the delivering tree.
- Not checked when merged: remote GitHub Actions CI workflows.
