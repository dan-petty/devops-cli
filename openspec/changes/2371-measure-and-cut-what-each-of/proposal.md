# Proposal

## Why

The full test suite on 16 xdist workers takes 287 s, but the tests account for only 151 s. The other 136 s is worker startup, repeated collection, and first-import costs of heavy libraries. Each worker pays the import cost of pydantic_ai, anthropic, kubernetes, and textual in the test that first uses them. #2371 asks to measure this overhead and apply the change with the largest share.

## What Changes

- Add a session-scoped fixture in tests/conftest.py that imports pydantic_ai, anthropic, kubernetes, and textual before any test runs on a worker.
- Add a test that verifies the session fixture pre-loads the heavy modules and that the fixture scope is session.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-job-time`: test-worker-import-preload

## Impact

- Tests: `tests/conftest.py`

## Feasibility

- The issue states 287 s total, 151 s tests, 136 s overhead, measured on 2026-10-27 on a 16-CPU host with 11,285 tests.
- tests/test_cli_startup_imports.py exists and uses python -X importtime, confirming the measurement approach is already in the codebase.
- CHANGELOG.md:1645 records that #1338 already deferred some heavy imports, so the remaining modules (pydantic_ai, anthropic, kubernetes, textual) are the target.
- The CI config uses -n logical --dist worksteal (CHANGELOG.md:1197), confirming 16 workers on a 16-CPU host.
- First check: uv run pytest tests/test_cli_startup_imports.py -v to confirm the import budget tests pass.
- Second check: uv run pytest --collect-only -q | wc -l to confirm the test count is near 11,285.
- Third check: uv run python -X importtime -c 'import pydantic_ai' to measure the import cost of the heaviest module.

## Existing Tool Considered

pytest-xdist is in use for parallel execution. python -X importtime is built into CPython and already used by tests/test_cli_startup_imports.py. pytest --durations and -v with xdist provide per-test timing and worker attribution. No new tool is needed. The session fixture uses pytest's built-in fixture system.
