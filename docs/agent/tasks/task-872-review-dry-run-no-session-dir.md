# Task: Dry-Run Review Writes No Session Directory or Findings (#872)

**Issue**: [#872](https://github.com/dan-petty/devops-cli/issues/872)
**Feasibility**: Verified against `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/ai/review/review_environment.py`, `src/devops_cli/ai/review/runner.py`, and `src/devops_cli/security/mypy.py`; confirmed `ReviewPipelineOrchestrator` previously created `session_dir` and `files_dir` and persisted `findings.json`, `candidates.json`, `findings.sarif`, `review.md`, and per-file `.json` payloads even when `is_dry_run()` was True.

## Summary

- Updated `ReviewPipelineOrchestrator` (`src/devops_cli/ai/review/pipeline.py`) and `_get_reviews_base_dir` (`src/devops_cli/ai/review/review_environment.py`) to skip directory creation (`session_dir`, `files_dir`), per-file payload persistence, and consolidated session artifact writes (`findings.json`, `candidates.json`, `findings.sarif`, `review.md`) when `is_dry_run()` is active, while still rendering the console preview.
- Updated `run_mypy_scan` (`src/devops_cli/security/mypy.py`) to return simulated dry-run findings immediately under `is_dry_run()` rather than invoking `mypy` in a subprocess.
- Added offline dry-run tests in `tests/test_review_path.py` covering both standard and routed-files-only review workflows and verifying `devops review stats` reports no saved sessions.

## Acceptance Criteria

- [x] An offline test points `_get_reviews_base_dir` at a tmp dir, sets `DEVOPS_CLI_DRY_RUN=true` and reviews a tmp target through the orchestrator path, asserting that the reviews dir stays empty and `devops review stats` reports no saved sessions (`tests/test_review_path.py::test_run_review_dry_run_skips_client_calls`).
- [x] `test_run_review_dry_run_skips_client_calls` in `tests/test_review_path.py` passes under 1 s (`tests/test_review_path.py::test_run_review_dry_run_skips_client_calls`).
- [x] The files not written include `findings.sarif` and `review.md` (`tests/test_review_path.py::test_run_review_dry_run_skips_client_calls`).
- [x] A dry run whose only change is a routed file leaves the reviews directory empty (`tests/test_review_path.py::test_dry_run_routed_files_only_leaves_reviews_dir_empty`).
- [x] `uv run devops ci` passes.
