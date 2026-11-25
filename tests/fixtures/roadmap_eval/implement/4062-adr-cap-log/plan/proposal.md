# Proposal

## Why

The alternatives ADR cap test failed on a loaded host because it read a warning from `opentelemetry.sdk.trace.export`. PR #4077 filters the records by logger name, but a telemetry test still shuts down the global tracer and leaves it in place. Later tests then export spans through the shut processor and log the warning (#4062).

## What Changes

- `test_tracer_lifecycle_reset_and_shutdown` calls `reset_tracer()` after it checks the shut tracer, so the next test gets a fresh tracer.
- The alternatives cap test emits one warning from the OpenTelemetry exporter logger and still asserts only the records of `devops_cli.roadmap.adr`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/telemetry/test_telemetry.py`, `tests/roadmap/test_roadmap_alternatives.py`

## Feasibility

- `reset_tracer` already builds a fresh global tracer.
- `caplog` already filters by logger name in the cap test.
- Verification commands: `uv run devops ci test tests/telemetry/test_telemetry.py tests/roadmap/test_roadmap_alternatives.py -n 0` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

`caplog` filters the records, and `reset_tracer` restores the tracer. No library is added.
