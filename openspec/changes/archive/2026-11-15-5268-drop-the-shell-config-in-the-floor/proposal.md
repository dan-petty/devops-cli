# Proposal

## Why

A devcontainer shell exports `DEVOPS_CLI_CONFIG` with the checkout's `config.yaml`. Six tests of `tests/docs` read settings before the per-test fixture set its own config, and the host path guard failed their setup and teardown (#5268).

## What Changes

- `tests/conftest.py` drops `DEVOPS_CLI_CONFIG` at import, before any test reads settings. The per-test `config` fixture still sets the variable of each test.
- Add `test_the_floor_drops_the_shell_config_variable` in `tests/invariants/test_hermetic_floor.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The test floor is not a behaviour of the product.

## Impact

- Tests: `tests/conftest.py`, `tests/invariants/test_hermetic_floor.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `tests/conftest.py:1138` sets `DEVOPS_CLI_CONFIG` per test, and the module imports no settings.
- The six tests fail with `DEVOPS_CLI_CONFIG=/workspaces/devops-cli/config.yaml` on main and pass after the change.
- `uv run pytest tests/docs/test_docs_source_argv_collector.py tests/docs/test_docs_synced_blocks.py` passes with that variable.

## Existing Tool Considered

The floor already drops the runner variable of #3990 in the fixture. The change drops this one at import: about 200 tokens to build and 20 a quarter to keep.

## Dependencies

None.
