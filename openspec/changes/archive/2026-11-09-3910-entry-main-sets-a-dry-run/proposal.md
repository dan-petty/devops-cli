# Proposal: #3910

## Why

Issue #3910 fixes a defect found while migrating root module tests in #3901 (item 3 of #1333). `entry.main` calls `set_dry_run(True)` when the argument vector contains `--dry-run`. The root callback `main` in `src/devops_cli/main.py` sets the dry-run state again before a command runs. The call in `entry.main` sets `_ACTIVATED_HERE = True`. This causes `dry_run_requested_by_environment()` to return `False`. When an exported `DEVOPS_CLI_DRY_RUN` variable meets a command that has its own `--dry-run` flag, the root callback clears the exported variable. This drops the dry-run request that the caller exported. Runs that stop before the root callback do not read `is_dry_run()`. Telemetry export reads `in_dry_run_invocation()`, which `mark_dry_run_invocation` already sets.

## What Changes

- Remove the call to `set_dry_run(True)` from `src/devops_cli/entry.py`.
- Remove the unused `set_dry_run` import from `src/devops_cli/entry.py`.
- Keep the `mark_dry_run_invocation(requested)` call in `src/devops_cli/entry.py`.
- Add tests in `tests/commands/test_entry_point.py` to confirm that an exported `DEVOPS_CLI_DRY_RUN` variable survives a command's own `--dry-run` flag.
- Add tests in `tests/commands/test_entry_point.py` to confirm that early-stop runs keep exit code 0 and output while recording `in_dry_run_invocation()`.
- Add a test asserting that `src/devops_cli/entry.py` does not import `set_dry_run`.
- This change alters no behavior that a consumer observes. It has no spec delta, and `skip_specs: true` is set.
- The change fits one pull request.

## Capabilities

This change adds no capability. It removes dead and conflicting state assignments in the CLI entry point.

## Impact

- `src/devops_cli/entry.py`
- `tests/commands/test_entry_point.py`

## Feasibility

Verified on `origin/main` at commit 84117ace.
1. `src/devops_cli/entry.py` imports `set_dry_run` and calls `set_dry_run(True)`.
2. `src/devops_cli/dry_run/state.py` sets `_ACTIVATED_HERE = True` on `set_dry_run(True)`.
3. `dry_run_requested_by_environment()` returns `is_dry_run() and not _ACTIVATED_HERE`.
4. In `src/devops_cli/main.py`, `requested = dry_run or dry_run_requested_by_environment()`, and `set_dry_run(requested)` runs.
5. Telemetry exit handler reads `in_dry_run_invocation()`, not `is_dry_run()`.
6. Removing `set_dry_run(True)` from `entry.py` ensures that `_ACTIVATED_HERE` remains `False` when `DEVOPS_CLI_DRY_RUN` is exported.

## Existing Tool Considered

Not applicable. This change removes redundant internal code and adds unit tests. The project test fakes and fixtures cover the requirements.
