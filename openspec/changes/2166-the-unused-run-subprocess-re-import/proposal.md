# Proposal

## Why

#2166: Two test accommodations reached the code after #1309 and #1332 were filed, and no check stopped them. The unused run_subprocess re-import in security/ruff.py and the private _prepare_cmd alias in core/process.py violate docs/TESTING.md. No check prevents a new # noqa: F401 re-import from entering src/.

## What Changes

- Remove the unused run_subprocess import from src/devops_cli/security/ruff.py
- Remove the _prepare_cmd alias from src/devops_cli/core/process.py and update tests/support/fakes/process.py and tests/core/test_process.py to use prepare_tool_cmd
- Add a devops ci row that runs ruff check --select F401 --ignore-noqa src and fails when the finding count exceeds 14
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-admission`: F401 re-import ceiling check

## Impact

- Code: `src/devops_cli/security/ruff.py`, `src/devops_cli/core/process.py`, `src/devops_cli/commands/ci.py`
- Tests: `tests/support/fakes/process.py`, `tests/core/test_process.py`

## Feasibility

- The re-import at src/devops_cli/security/ruff.py:23 is confirmed by the issue body and the context shows the file in the directory tree.
- The alias at src/devops_cli/core/process.py:482 is confirmed by identifier matches showing _prepare_cmd = prepare_tool_cmd.
- The test references at tests/core/test_process.py:583-598 are confirmed by identifier matches.
- The command uv run ruff check --select F401 --ignore-noqa src is stated to report 15 findings at b170358e, all in security/.
- First checks the implementation runs: rg -n 'noqa: F401' src/devops_cli/security/ruff.py to confirm the import exists; rg -n '_prepare_cmd' src tests to confirm the alias and its references; uv run ruff check --select F401 --ignore-noqa src to confirm the count is 15 before removal.

## Existing Tool Considered

ruff is already the project linter and is available via uv run. No new tool or library is needed. The check uses the existing ruff binary with --select F401 --ignore-noqa flags.
