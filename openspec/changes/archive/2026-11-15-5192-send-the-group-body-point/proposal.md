# Proposal

## Why

`devops ci` and `devops gh` run the body of the command group with no sub-command. `OTelTyper.callback` wrapped that body only in `_report_devops_error`, so the run sent no point to `devops_cli_subcommand_duration_seconds`. The golden signals of the dashboard read that histogram, so the latency, traffic and error share of 831 `ci` runs and 429 `gh` runs in 24 h was missing (#5192).

## What Changes

- `OTelTyper.callback` traces a body whose context names no sub-command, with `_execute_traced_cli_command`.
- A callback that runs with a sub-command keeps the old wrapper, so the group and the sub-command do not both send a point.
- The group body names the group in `command` and `sub_command`, as a command with no group does.
- Add `test_a_group_body_sends_the_subcommand_histogram_point` in `tests/telemetry/test_telemetry.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: a command group that runs its own body sends the sub-command histogram point.

## Impact

- Code: `src/devops_cli/core/cli.py`
- Tests: `tests/telemetry/test_telemetry.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/core/cli.py:281:def command(` wraps each command in `_execute_traced_cli_command`, and `:299:def callback(` wraps the group body only in `_report_devops_error`.
- `src/devops_cli/core/cli.py:22:def _subcommand_labels(` gives `command` and `sub_command` from the Click command path, so `devops ci` gives `ci` and `ci`.
- Click sets `Context.invoked_subcommand` before it invokes the callback, so the wrapper tells a body run from a run of a sub-command.
- `uv run pytest tests/telemetry` passes after the change.

## Existing Tool Considered

Click and the OpenTelemetry client already give the context and the histogram. The change adds one branch in the callback wrapper: about 1,000 tokens to build and 100 a quarter to keep.

## Dependencies

None.
