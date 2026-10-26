# Design

## Context

See `proposal.md` for motivation. In `src/devops_cli/commands/dashboard.py`, `_resolve_initial_tab(tab: str)` converts numeric tab indexes and domain names to tab identifiers. When an invalid tab name is provided, `_resolve_initial_tab` formats it as `f"tab-{cleaned}"`. Textual then raises an unhandled `ValueError` when initializing `TabbedContent`. Furthermore, `refresh_all` in `src/devops_cli/ui/refresh.py` has no callers.

## Goals / Non-Goals

**Goals:**
- Validate the `--tab` argument at the command boundary before dashboard execution.
- Raise a typed `ValidationError` from `devops_cli.exceptions.validation` on unknown tab values.
- Name all valid tab values in the error message.
- Use `exit_on_error(ValidationError)` to exit cleanly with code 1 and no traceback.
- Remove `refresh_all` from `src/devops_cli/ui/refresh.py` and its test.

**Non-Goals:**
- Add new dashboard tabs or change existing tab identifiers.
- Modify Textual internals or `TabbedContent` error handling.

## Decisions

### Decision: Validate tab in `_resolve_initial_tab` and raise `ValidationError`
We validate `tab` in `_resolve_initial_tab` against `TAB_NUM_MAP`. If `cleaned` is not present, we raise `ValidationError` referencing `ERRORS.dashboard.unknown_tab`. The error message is formatted with the input value and `", ".join(CONST_DASHBOARD_DOMAINS)`.
- *Alternative rejected*: Catch `ValueError` from Textual `DashboardApp.run()`. Evidence that rejected it: `devops dashboard --summary` and non-TTY invocations bypass `DashboardApp.run()`, allowing invalid `--tab` values to pass unvalidated. Catching `ValueError` also masks internal widget bugs.
- *Alternative rejected*: Rely on Typer `click.BadParameter`. Evidence that rejected it: `devops-cli` standardizes domain errors on `DevOpsCLIError` subclasses to ensure consistent error codes and exit codes (`docs/ERRORS.md`).

### Decision: Wrap tab resolution in `exit_on_error(ValidationError)`
In `_run_dashboard_or_summary`, tab resolution is wrapped in `exit_on_error(ValidationError)` before checking for summary or non-TTY mode. This guarantees invalid tabs fail immediately across interactive and headless modes.
- *Alternative rejected*: Allow `ValidationError` to bubble to the root runner. Evidence that rejected it: `main.py` logs unhandled exceptions with full stack traces in debug logs and wraps them in generic errors instead of clean CLI outputs.

### Decision: Delete unused `refresh_all`
Search confirmed `refresh_all` has zero callers across `src/`. Removing it eliminates dead code and simplifies `src/devops_cli/ui/refresh.py`.
- *Alternative rejected*: Keep `refresh_all` for potential future use. Evidence that rejected it: Project rule in `AGENTS.md` forbids shims and unused code before 1.0.0.

## Risks / Trade-offs

- [Risk: Scripts passing tab numbers or names with surrounding spaces or mixed case fail] → Mitigation: `tab.strip().lower()` normalizes inputs before dictionary lookup.
