# Design

## Context

The root `tests/conftest.py` resets process-wide state of `src` modules after every test (#1310). The reset of the logfire bridge calls `shutdown`, but it does not turn the console off or uninstrument pydantic-ai. `tests/telemetry/test_telemetry_llm_content.py` calls `logfire.configure` for real, so the console state reaches the next test of the worker.

## Goals

- Turn the console off and uninstrument pydantic-ai after every test.
- Cost nothing for the tests that load neither module.

## Decisions

- **A support helper, a conftest fixture.** `tests/support/logfire_isolation.py` holds `quiet_logfire`, and the autouse fixture in `tests/conftest.py` calls it. A test can unit-test the helper, and the fixture keeps the reset in one place.
- **`sys.modules` gates the reset.** A test that never loads logfire or pydantic-ai has no state to reset. The check also keeps the fixture away from a module that is not installed.
- **Teardown, not setup.** The reset runs after the test, so a test that asserts console spans keeps its assertion. The teardown runs for a failed test too.

## Risks

- `logfire.configure(console=False)` replaces the global configuration of a test that wanted a configured logfire after the test. No test reads logfire state after its own teardown.

## Tests

- The helper calls `logfire.configure(console=False)` and `Agent.instrument_all(False)`, in that order.
- The logfire content tests and the implement command tests pass in one worker in both orders.
