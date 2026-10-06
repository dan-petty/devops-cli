# Task: CI Gate Cache Certifies Only the Tree It Checked (#838)

**Issue**: [#838](https://github.com/dan-petty/devops-cli/issues/838)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/ci

## Description

The CI execution cache verifies whole-tree state against deterministic Git and blob fingerprints, certifying only the exact tree that passed all checks.

- **File-Subset Caching Removal** (`src/devops_cli/ci/cache.py`, `src/devops_cli/commands/ci.py`):
  - Removed legacy subset matching helpers: `_compute_file_hashes`, `_collect_modified_git_files`, `_is_subset_file_matching`, and `_check_pre_commit_subset_match`.
  - Removed `file_hashes` attribute from `CICacheEntry` and signatures of `save_ci_cache` and `get_ci_cache`.
  - Removed `--files` option and `_collect_ci_target_files` from `commands/ci.py` and `src/devops_cli/lang/en/help.py`.
  - Updated `FileOrSubcommandGroup` to eliminate file routing overrides (`resolve_command` and `cmd is None` branch in `invoke`), tracking only help flags on subcommands. Positional file arguments and `--files` flags raise Click `UsageError` with exit code 2 and 0 check executions.
  - Added dedicated `@app.command() def devcontainer` under `ci.py` to match the check table spec.
- **Tree Certification & Pre-Run Fingerprinting** (`src/devops_cli/commands/ci.py`, `src/devops_cli/ci/cache.py`):
  - Updated `compute_workspace_fingerprint` to return a 2-tuple: `(fingerprint, head_sha)`.
  - In `all_checks`, computed `before_fingerprint` prior to running checks on full, non-dry runs.
  - In `_try_save_ci_cache`, recomputed the fingerprint after all checks passed. If the working tree changed during the run (`fingerprint != before_fingerprint`), printed warning `MESSAGES.ci.cache_tree_changed` and returned without saving, leaving any existing cache file untouched and exiting 0 with the passing verdict.
- **Test Suite Updates** (`tests/test_ci_cache.py`, `tests/test_ci.py`):
  - Removed legacy subset tests (`test_get_ci_cache_pre_commit_subset_match` and `test_ci_cli_positional_files_pre_commit`).
  - Added `test_any_tracked_change_misses_the_cache` parametrised across `src/`, `tests/`, `docs/`, and `pyproject.toml`.
  - Added `test_a_file_argument_is_a_usage_error` covering positional and `--files` arguments.
  - Added `test_a_tree_edited_during_the_run_is_not_recorded` asserting warning emission, zero cache saves, and intact existing cache files when working tree mutates during execution.
  - Updated 2-tuple unpacking in `test_ci.py` and `test_ci_cache.py`.

## Acceptance Criteria

- [x] Legacy file-subset caching path (`--files`, `FileOrSubcommandGroup` file routing, `_collect_ci_target_files`, `_compute_file_hashes`, `_collect_modified_git_files`, `_is_subset_file_matching`, `_check_pre_commit_subset_match`, and `file_hashes` on `CICacheEntry`) is completely removed.
- [x] `compute_workspace_fingerprint` returns a 2-tuple `(fingerprint, head_sha)`.
- [x] In `all_checks`, fingerprint is computed before checks execute for full, non-dry runs. Recomputed upon completion: if tree mutated during run, `MESSAGES.ci.cache_tree_changed` warning is printed, existing cache is untouched, and exit code is 0.
- [x] Positional file arguments and `--files` options raise Click `UsageError` with exit code 2 and 0 check executions.
- [x] All new and updated tests execute offline in $< 1$s each.
- [x] `changelog.d/838.md` created; `CHANGELOG.md` and `docs/ROADMAP.md` remain untouched.
- Pending a person: `uv run devops ci` passes on this branch.
