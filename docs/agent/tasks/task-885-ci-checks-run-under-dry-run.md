# Task: devops ci Checks Run for Real Under the Gate (#885)

**Issue**: [#885](https://github.com/dan-petty/devops-cli/issues/885)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/ci

## Description

Under a dry run (`is_dry_run() is True`), `devops ci` checks, runners, and subcommands start zero subprocesses and mutate no external state.

- **Runner Guards** (`commands/ci.py`):
  - In `_run` and `_execute_check_async`, execution branches on `is_dry_run()` before invoking any process runner. Each builds a `PlannedRequest` containing the exact argv that would execute, including the `--preview-features malware-check,check-command` flag inserted when the command begins with `uv`.
  - Single check subcommands (`lint`, `format`, `test`, `coverage`, `typecheck`, etc.) call `_run`, which renders a one-request execution plan via `render_request_plan` and returns `True`.
  - `devops ci --dry-run` and `devops ci run --dry-run` build ordered execution requests—the pre-fix steps when fixes are enabled (`format_fix`, `lint_fix`, `docs_fix`), followed by every row in `get_check_specs()`—and render the aggregate plan via `render_request_plan`.
  - Dry-run `CheckResult` instances carry `dry_run=True` and `passed=False`. The gate prints no pass badges and no pass summary table for dry-run checks.
  - `_handle_ci_results` returns early without saving or clearing gate cache when `is_dry_run()` is active.
- **Artifact Protection** (`commands/ci.py`):
  - `_clean_coverage_artifacts` checks `if is_dry_run(): return`, preventing unlinking of `.coverage*` or `coverage.xml` files during dry runs.
- **Coverage Index Preview** (`commands/ci.py`):
  - `devops ci coverage --build-index --dry-run` plans the test run with `--cov-context=test` and environment variable `COVERAGE_CORE=ctrace` via `_run`. It computes no hashes and writes no index file to disk.
- **Test Suite** (`tests/test_ci_dry_run.py`):
  - Completely rewritten to record `subprocess.run` invocations rather than patching `_run`. Verifies zero subprocess calls across dry runs, preservation of coverage artifacts, one-request plans for subcommands, aggregate plans for full gate runs, and that live execution without `--dry-run` reaches the process runner.

## Survey of `--dry-run` Command Paths

An audit of 80 argument-free command paths declaring `--dry-run` verified that, apart from `ci`, the only subprocesses started were read-only:
- `git worktree list`
- `git rev-parse`
- `gh api rate_limit`
- `kubectl apply -k . --dry-run=client`

The 40 argument-taking `--dry-run` command paths are filed under candidate #986 for follow-up audit and preview alignment.

## Acceptance Criteria

- [x] Under a dry run, `_run` and `_execute_check_async` start no process. Each records a `PlannedRequest` holding the argv as it would run, including the `uv --preview-features` insertion.
  - `devops ci lint|format|test|coverage --dry-run` each print a one-request plan.
  - `devops ci --dry-run` and `devops ci run --dry-run` print, in order, the fix steps (when fixes are on) and then every row of `get_check_specs()`.
  - Each exits 0 with the `subprocess.run` recorder at zero calls (`tests/test_ci_dry_run.py`).
- [x] Dry-run `CheckResult`s carry a dry-run marker (`dry_run=True`) instead of `passed=True` for checks that never ran. The gate prints no pass badges or pass summary for them. Under a dry run, `_handle_ci_results` neither saves nor clears the cache.
- [x] `devops ci coverage --build-index --dry-run` plans the index run (`--cov-context=test` with env `COVERAGE_CORE=ctrace`), hashes nothing and writes no index. Tested with index path under `tmp_path`, verifying no file is created and the recorder sees zero calls.
- [x] `devops ci --dry-run` and `devops ci run --dry-run` unlink nothing: with `PYTEST_CURRENT_TEST` removed and `_get_project_root` pointed to `tmp_path` holding `.coverage.sample` and `coverage.xml`, both files still exist afterwards.
- [x] Without the flag, `devops ci lint` calls the runner once with `uv --preview-features malware-check,check-command run ruff check --fix .`, and `devops ci --no-cache` with the recorder reaches the runner for every check row.
- [x] `tests/test_ci_dry_run.py` contains zero occurrences of patching `commands.ci._run`.
- [x] `devops ci maintain --dry-run` output is unchanged (`tests/test_ci_maintain.py::test_ci_maintain_dry_run` passes).
- [x] The new and rewritten tests take at most 1 s in total for setup, call and teardown on one worker (measured at 0.52 s call duration).
- [x] The task file records the recorder results for the 80 argument-free `--dry-run` paths (the four read-only processes) and names #986 for the 40 argument-taking paths.
- [x] `changelog.d/885.md` exists; `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
- Pending a person: `uv run devops ci` passes on this branch.

## Measurements

Measured with `uv run pytest -n 0 --durations=0 tests/test_ci_dry_run.py`:

| Test | Call Duration |
| :--- | ---: |
| `test_ci_live_control` | 0.15 s |
| `test_other_ci_subcommands_dry_run` | 0.11 s |
| `test_ci_lint_dry_run` | 0.11 s |
| `test_ci_dry_run_unlinks_nothing` | 0.04 s |
| `test_ci_test_dry_run` | 0.02 s |
| `test_ci_coverage_dry_run` | 0.02 s |
| `test_ci_coverage_build_index_dry_run` | 0.02 s |
| `test_ci_format_dry_run` | 0.02 s |
| `test_ci_run_command_dry_run` | 0.02 s |
| `test_ci_all_checks_dry_run` | 0.01 s |
| **Total Call Time** | **0.52 s** |
