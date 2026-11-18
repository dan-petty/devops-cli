# Proposal: #4938

## Why

`devops ci fail-to-pass --base origin/main` prints a raw Python traceback when the serial base
pytest run passes the process-runner limit. `_run_pytest_replay` does not catch
`subprocess.TimeoutExpired`, and the run can take 1,800 seconds on a loaded host. Closes #4938.

## What Changes

- `_run_pytest_replay` catches a timeout and returns a could-not-run result with the limit.
- The report names the process-runner limit and the test files, and prints no pytest exit status
  that pytest did not return.
- The base, plain-base, head and gate-row replays use the same timeout handling.
- A timed-out replay exits 1, the command's existing could-not-run status.

## Capabilities

### Modified

- `ci-fail-to-pass`: a timed-out replay is a could-not-run result.

## Impact

A loaded host no longer turns a base replay into a traceback. The author sees the limit and the
test files, and the command exits 1. A serial base replay still runs; this change does not make it
parallel.

## Feasibility

Confirmed against the issue and the code: `_run_pytest_replay` in `src/devops_cli/ci/fail_to_pass.py`
calls `run_subprocess` with the default limit and catches no timeout. The command exits 1 when the
report is unsatisfied. The refine design records the reproduction at load 50.

## Existing Tool Considered

No open tool covers this need. pytest-timeout 2.4.0 enforces a per-test limit inside pytest; it
cannot catch the process-runner timeout, name the 1,800 second limit and test files, or set the
command's exit status. The in-repo change costs about 1,500 tokens to build, 300 to keep and fix,
and about one hour.
