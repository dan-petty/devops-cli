# Proposal: #4926

## Why

`devops test run --changed` prints a Python traceback when pytest runs longer than the subprocess
timeout. `run_test_cmd` (`src/devops_cli/commands/test_cmd.py:195`) calls `run_subprocess`, and
`subprocess.TimeoutExpired` goes up through `core/process.py` with no handler. The output is about
480 lines: the traceback and the full pytest argument list of 421 test modules. The command does not
name the 1800-second limit or the option that changes it. Closes #4926.

## What Changes

- `run_test_cmd` catches `subprocess.TimeoutExpired` and raises a `DevOpsCLIError` that names the
  effective timeout in seconds and the `--timeout` option, so the one exit seam prints one error
  line and exits 1 with no traceback.
- `devops test run` gains a `--timeout` option, default 1800 seconds, and passes its value to
  `run_subprocess`.
- A pytest failure that is not a timeout keeps its output and exit status.

## Capabilities

`test-run-timeout` (new): how `devops test run` reports and bounds a pytest subprocess timeout.

## Impact

- A timeout gives one error line that names the limit and the option, not a traceback.
- The default limit is unchanged at 1800 seconds.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: `run_subprocess` takes a `timeout` argument
  (`src/devops_cli/core/process.py:1171`), and the exit seam of `new_typer()` reports a
  `DevOpsCLIError` as one line with its status (`src/devops_cli/core/cli.py:361`). Both exist.
- The 2026-11-15 alternatives check found no tool that converts `subprocess.TimeoutExpired` into a
  `DevOpsCLIError`; the fix is local code.

## Existing Tool Considered

`subprocess.TimeoutExpired` and the repository's `DevOpsCLIError` cover the need. The fix is a few
lines in `run_test_cmd`. No open, maintained tool converts a subprocess timeout into this project's
error type, and the 2026-11-15 alternatives check found none.
