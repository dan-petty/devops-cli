# Proposal

## Why

Issue #2170: Five test modules set `live` marks at module level with `pytestmark`. This mark permits every test in the module to start the named external programs. If a test starts an external program by mistake, the hermetic floor allows it. Moving the `live` mark to individual tests ensures that only tests that need external programs can execute them.

## What Changes

- Remove module-level `pytestmark` definitions with `live` marks from five modules:
  - `tests/commands/test_ci.py`
  - `tests/core/test_process.py`
  - `tests/core/test_subprocess_env_boundary.py`
  - `tests/config/test_isolation_tripwire.py`
  - `tests/commands/test_cli_startup_imports.py`
- Add `@pytest.mark.live(...)` to each individual test function that executes the named program.
- Verify that tests that do not declare `live` marks fail at the hermetic floor if they start external programs.
- Keep all test assertions and behaviors intact.
- Set `skip_specs: true` in `.openspec.yaml`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Test files under `tests/commands/`, `tests/core/`, and `tests/config/`.
- No production source files under `src/` are changed.

## Feasibility

- The conftest fixture `configure_edge_markers` reads markers per node using `request.node.iter_markers("live")`.
- When module-level `pytestmark` is removed, node-level markers on test functions are read correctly.
- Removing module-level marks causes tests that start unlisted binaries to fail immediately at the hermetic floor.

## Existing Tool Considered

pytest built-in markers (`pytest.mark.live`). No custom marker framework is built.
