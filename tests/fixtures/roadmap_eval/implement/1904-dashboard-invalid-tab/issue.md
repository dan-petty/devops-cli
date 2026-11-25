## Problem

`devops dashboard --tab <value>` with a value that names no tab ends with a Python traceback: `ValueError: No Tab with id '--content-tab-<value>'`. A user sees the traceback and not a message that names the valid tabs.

## Evidence

- A headless run of `DashboardApp` with `initial_tab` set to `tab-nope`, `tab-ai` and `tab-5` ends with `ValueError No Tab with id '--content-tab-tab-nope'` and the same text for the two other values.
- Every unknown value did this before the change that deleted the AI Review tab (#1883). The values `ai` and `5` were valid before that change, so they now hit the same fault.
- The project rule says that domain errors raise typed exceptions from `DevOpsCLIError` with an exit code and a machine-readable error code (`docs/ERRORS.md`).
- `refresh_all` in `src/devops_cli/ui/refresh.py` has no caller in `src`. It had none before #1883 either.

## Remedy

Reject an unknown `--tab` value at the command boundary with a typed error. The message names the valid tab values. The test uses the real value list of the dashboard, not a copy of it. Delete `refresh_all` if a search confirms that nothing calls it.
