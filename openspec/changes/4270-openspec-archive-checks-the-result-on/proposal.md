# Proposal: #4270

## Why

`uv run devops openspec archive <change>` can print `Archived <change>. Every spec and change validates.` and move nothing. The wrapper decides success from exit codes only. In a dry run, `run_subprocess` starts no process and returns exit code 0, so `devops --dry-run openspec archive no-such-change-zz` and `DEVOPS_CLI_DRY_RUN=1 devops openspec archive no-such-change-zz` print `Archived` for a change that does not exist. A false `Archived` sends a pull request on without its archive commit. Closes #4270.

## What Changes

- `archive_change` reads the result on disk after the `openspec archive` run exits 0. The folder `openspec/changes/<change>` must be gone, and a new folder `openspec/changes/archive/<date>-<change>` must exist. If a check fails, it raises `ToolExecutionError` that names the change and the folder, and the validation does not run.
- `devops openspec archive` gets a `--dry-run` option. In a dry run (the option, `devops --dry-run`, or `DEVOPS_CLI_DRY_RUN=1`) it starts no process, lists the two `openspec` commands it would run, and says `Would archive <change>`. It does not say `Archived`.
- `OpenSpecFake` moves the folder of a change when a recorded `archive` run succeeds, as the real tool does. `script` takes an `effect` for a test that needs a file change of its own.
- Tests: `tests/openspec/test_openspec_archive.py`. The old test `test_archive_in_a_dry_run_executes_as_no_external_request` asserted the false `Archived` output, so it is removed.

## Capabilities

### New Capabilities

- `openspec-archive`: The archive command reports success only when the change folder moved, and plans without running in a dry run.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/openspec/archive.py`, `src/devops_cli/commands/openspec.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/openspec/test_openspec_archive.py`, `tests/core/test_openspec_command.py`, `tests/support/fakes/openspec.py`.
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/openspec.md` (generated).

## Feasibility

Checked on 2026-11-09 with the pinned `openspec` 1.14.3 and the code of `main`:

- `uv run devops --dry-run openspec archive no-such-change-zz` printed `Archived ... Every spec and change validates.` and exited 0 on `main`. The seven new tests fail on `main` (`DID NOT RAISE`, `Archived` in the output).
- `core/process.py` returns a `PlannedProcessResult` with exit code 0 in dry-run mode, and `OpenSpecTool.run` passes `quiet=True`.
- A real `openspec archive 1-demo --yes --json` in a scratch tree moved the folder to `openspec/changes/archive/2026-11-09-1-demo` and printed that path. `openspec archive nope --yes --json` exited 1 with `archive_change_not_found`.

## Existing Tool Considered

`openspec archive --json` (1.14.3) prints the archive path. It does not cover the failure: a process that did not run prints nothing, so a check of the folders on disk is still needed. A parse of the JSON would add code and change the error output of the tool (it prints JSON, not text, on failure) and the recorded runs. The disk check is about 25 lines and adds no dependency. `render_request_plan` and `PlannedRequest` already give the dry-run output.
