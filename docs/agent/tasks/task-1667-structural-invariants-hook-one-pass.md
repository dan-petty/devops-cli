# Task: Structural Invariants Hook Runs in One Pass Without uv Sync (#1667)

**Issue**: [#1667](https://github.com/dan-petty/devops-cli/issues/1667)
**Scope**: scope/ci
**Feasibility**: Runtime analysis confirmed that `src/devops_cli/core/code_metrics.py` imports exclusively from Python's standard library (`argparse`, `ast`, `sys`, `dataclasses`, `pathlib`, `collections.abc`), requiring zero virtual environment packages or `devops_cli` submodules. Running the hook via `uv run` forced full venv synchronization (bytecode verification of 17,900+ files and OSV malware network queries) across up to 16 parallel batches, taking 15s–100s. Direct invocation via `python3 -P src/devops_cli/core/code_metrics.py` with `require_serial: true` drops execution time from 2.8s per file (and 17s+ for 20 files) to under 0.10s in a single process.

| Metric | Before (`uv run`) | After (`python3 -P`, `require_serial: true`) |
|---|---|---|
| 1 file execution | 1.43s – 2.80s | 0.05s – 0.09s |
| 20 staged files | 17.2s (5 syncs, queue contention) | 0.09s (1 process, 0 syncs) |
| OSV / network dependence | Required (fails commit if OSV hung/offline) | None (pure stdlib execution) |

## Description

- [x] Updated `.pre-commit-config.yaml` to configure `structural-invariants` with entry `python3 -P src/devops_cli/core/code_metrics.py` and `require_serial: true`, retaining `args: [--max-depth, "5"]`.
- [x] Updated hook comment in `.pre-commit-config.yaml` to explain the direct standard library invocation without package inits or virtual environment synchronization overhead.
- [x] Updated `src/devops_cli/core/code_metrics.py` module docstring to reference the new direct Python entry point.
- [x] Updated pinned-entry unit test `test_the_commit_hook_runs_this_module_at_the_default_cap` in `tests/test_code_metrics.py` to assert the new entry string, arguments, and `require_serial: true`.
- [x] Added `test_the_hook_entry_matches_module_execution_on_valid_and_breaching_files` in `tests/test_code_metrics.py` verifying that the configured hook command behaves identically to `code_metrics.main()` on both conforming and depth-breaching files in a `tmp_path` workspace.
- [x] Added `test_pre_commit_runs_hook_in_single_process_across_multiple_files` in `tests/test_code_metrics.py` asserting that pre-commit invokes the hook in a single process across multiple staged files.
- [x] Added changelog fragment `changelog.d/1667.md` under `### Changed`.
- [x] Verified full test suite and quality gate pass via `uv run devops ci`.
