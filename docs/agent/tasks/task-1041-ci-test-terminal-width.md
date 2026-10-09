# Task: CLI help renders at the same width locally and in GitHub CI (#1041)

**Issue**: [#1041](https://github.com/dan-petty/devops-cli/issues/1041)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: type/bug, priority/p2-medium, scope/ci

## Description

Under GitHub Actions, Typer sets `FORCE_TERMINAL = True` at import when `GITHUB_ACTIONS` is set in the environment. In the test suite, `tests/conftest.py` sets `COLUMNS=250`, `NO_COLOR=1`, and `TERM=dumb`. When Rich initializes a console that is forced to be a terminal with `TERM=dumb`, it defaults to an 80x25 terminal size and ignores `COLUMNS`. Without `GITHUB_ACTIONS`, Rich treats the non-terminal console normally and respects `COLUMNS=250`.

This caused CLI help panels invoked via `CliRunner` to wrap at 80 columns in GitHub Actions CI while rendering at 250 columns locally and in DevContainers, creating width-dependent test discrepancies and line-wrap failures.

The fix configures `tests/conftest.py` to set `typer.rich_utils.FORCE_TERMINAL = None` upon import and during `reset_dry_run_state`, ensuring test consoles consistently respect `COLUMNS=250` across all environments.

## Acceptance Criteria

- [x] Tests see one terminal width in every environment: `tests/conftest.py` stops Typer's GitHub Actions detection from forcing a terminal for test consoles by clearing `typer.rich_utils.FORCE_TERMINAL = None`, so Rich always reads `COLUMNS`.
- [x] A test asserts that, with `GITHUB_ACTIONS=true` in the environment, a `CliRunner` render of a help panel uses the conftest width (no line of the help is wrapped at 80 columns): `test_cli_help_panel_renders_at_conftest_width_under_github_actions` in `tests/test_output.py`.
- [x] The full suite passes with `CI=true GITHUB_ACTIONS=true` set locally, and without them.
- [x] `changelog.d/1041.md` records the fix under `### Fixed`. `CHANGELOG.md` is not edited.
- [x] `uv run devops ci` passes.
