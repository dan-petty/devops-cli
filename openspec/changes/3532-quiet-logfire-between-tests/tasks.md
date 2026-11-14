# Tasks

## 1. Quiet logfire between tests

Reads: `tests/conftest.py`, `tests/telemetry/test_telemetry_logfire.py`. Changes: the same files and `tests/support/logfire_isolation.py`.

- [ ] 1.1 Add `tests/support/logfire_isolation.py` with `quiet_logfire`, which reads `logfire` and `pydantic_ai` from `sys.modules` and calls `logfire.configure(console=False)` and `Agent.instrument_all(False)` when each is loaded.
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_logfire.py` passes
- [ ] 1.2 Add the autouse fixture `quiet_logfire_console` to `tests/conftest.py` and call the helper in its teardown.
  - Verification: both test files of the leak pass in one worker in both orders
- [ ] 1.3 Add a test that the helper turns both switches off.
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_logfire.py` passes
