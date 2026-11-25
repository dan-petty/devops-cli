# Proposal

## Why

Issue #1904 reports that passing an invalid value to `devops dashboard --tab <value>` causes an unhandled `ValueError` exception traceback. The user receives a raw stack trace instead of a clear error message that lists the valid tab values. This change fits one pull request.

## What Changes

This change alters user-observable CLI behavior:
- Validates the `--tab` option value at the command boundary against configured dashboard domains and numeric indexes.
- Rejects unknown tab identifiers with a typed `ValidationError` that prints a user-friendly error message and exits cleanly.
- Names the valid tab values in the error message.
- Removes the unused function `refresh_all` from `src/devops_cli/ui/refresh.py` and its test.

## Capabilities

### New Capabilities
- `workstation-dashboard`: Command line options and terminal user interface behavior for the workstation dashboard command.

### Modified Capabilities

## Impact

- Affected code:
  - `src/devops_cli/commands/dashboard.py`: Validate `--tab` input and handle validation error with `exit_on_error(ValidationError)`.
  - `src/devops_cli/lang/en/errors.py`: Add `DashboardErrorMessages` with `unknown_tab` template string.
  - `src/devops_cli/ui/refresh.py`: Remove `refresh_all`.
  - `tests/test_ui_dashboard.py`: Add CLI tests asserting invalid `--tab` rejection using `CONST_DASHBOARD_DOMAINS`.
  - `tests/test_ui_reactive.py`: Remove tests for `refresh_all`.

## Feasibility

The premise was confirmed against the current codebase:
1. Executing `DashboardApp(initial_tab="tab-nope")` causes Textual `TabbedContent` to raise `ValueError: No Tab with id '--content-tab-tab-nope'`.
2. `src/devops_cli/commands/dashboard.py` maps tab strings without verifying their presence before running the terminal user interface or summary.
3. Codebase search confirms `refresh_all` in `src/devops_cli/ui/refresh.py` has zero callers in `src/`.

## Existing Tool Considered

Typer and Click handle argument validation, but custom domain exceptions in `devops-cli` use `DevOpsCLIError` subclasses to ensure consistent machine-readable error codes and exit codes. `ValidationError` from `devops_cli.exceptions.validation` already exists and provides this behavior.

Internal code deleted by this change:
- `refresh_all` in `src/devops_cli/ui/refresh.py` (12 lines).
- `test_refresh_all_publishes_every_requested_domain` in `tests/test_ui_reactive.py` (8 lines).
