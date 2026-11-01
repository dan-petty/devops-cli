# Proposal

## Why

Issue #2369 reports that tests/commands/test_cli_startup_imports.py takes 204 s of the suite's 2,423 s. Each of its 56 probes starts a fresh interpreter under -X importtime, which adds per-import overhead to stderr and a Python parse of that text. The file is a structural budget and must stay, but its cost is the problem.

## What Changes

- Replace -X importtime with a sys.modules dump in the normal probe path
- Add a timed re-probe that runs with -X importtime only when a budget fails
- Keep all 56 probes, all four limits, and the control test unchanged
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-job-time`: startup-import-probe-mechanism

## Impact

- Tests: `tests/commands/test_cli_startup_imports.py`

## Feasibility

- The issue confirms the cost: 56 probes at about 4.2 s CPU each, with -X importtime adding per-import stderr lines and a Python parse. The file is at tests/commands/test_cli_startup_imports.py, and line 448 defines _probe_startup_imports.
- sys.modules provides the set of loaded module names at the end of a run, which is all the budget count needs. The identifier matches confirm the four limit constants at lines 33-36 of the file.
- First checks: run pytest tests/commands/test_cli_startup_imports.py -n 0 to get the baseline CPU time. Then run the same command after the change and confirm the total is at most half the baseline over three runs.

## Existing Tool Considered

python -X importtime is the existing tool. It stays for the failure diagnostic message. The normal probe uses sys.modules, a Python built-in that requires no new dependency. No new tool is introduced.
