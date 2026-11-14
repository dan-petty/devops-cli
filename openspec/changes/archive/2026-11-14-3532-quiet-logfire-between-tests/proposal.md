# Proposal

## Why

A test that calls `logfire.configure` with the console on and calls `logfire.instrument_pydantic_ai` leaves that state for the next test of the same xdist worker. `tests/roadmap/implement/test_roadmap_implement_command.py::test_a_done_step_prints_its_outcome_as_json_and_exits_0` then fails with `JSONDecodeError: Extra data`, because the stdout holds console spans (#3532).

## What Changes

- `tests/support/logfire_isolation.py` adds `quiet_logfire`, which turns the logfire console off and uninstruments pydantic-ai when either module is loaded.
- An autouse fixture in `tests/conftest.py` calls it after every test, a failed test included.
- A test in `tests/telemetry/test_telemetry_logfire.py` proves both switches.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/conftest.py`, `tests/support/logfire_isolation.py`, `tests/telemetry/test_telemetry_logfire.py`

## Feasibility

- `logfire.configure(console=False)` and `Agent.instrument_all(False)` are the switches that `src/devops_cli/telemetry/logfire.py` and `src/devops_cli/telemetry/library_spans.py` already use.
- The fixture reads `sys.modules`, so a test that loads neither module pays no cost.
- Verification commands: `uv run devops ci test tests/telemetry/test_telemetry_logfire.py`, both files in one worker in both orders, and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

pytest already gives the autouse fixture, and the failed-test teardown comes with it. logfire and pydantic-ai give the two switches. No new dependency.
