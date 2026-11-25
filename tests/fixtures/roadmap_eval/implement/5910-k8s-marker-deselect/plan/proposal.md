# Proposal: #5910

## Why

A default test run deselects every test under `tests/k8s/`: 819 tests, offline tests included. `_deselect_by_marker(config, items, "k8s")` in `tests/conftest.py` checked `"k8s" in item.keywords`. pytest puts parent package and directory names in `item.keywords`, so the package `tests/k8s` matched and caused all tests under `tests/k8s/` to be deselected.

## What Changes

- `tests/conftest.py`: update `_deselect_by_marker` to inspect `item.get_closest_marker(marker) is not None` instead of `marker in item.keywords`.
- `tests/invariants/test_hermetic_floor.py`: add `test_a_default_run_deselects_only_tests_marked_k8s` to verify that an unmarked test under a `k8s/` directory runs while a marked test is deselected by default.
- This change alters no consumer-observed CLI behaviour or command syntax, so it sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The test selection filter is internal to test runner execution and not an external capability.

## Impact

- Offline tests under `tests/k8s/` run again in CI test runs.
- Live k8s tests carrying the `@pytest.mark.k8s` mark continue to be deselected by default and selected with `-m k8s`.

## Feasibility

- Confirmed on `origin/main`: `uv run pytest -n 0 --co -q tests/k8s/` deselected 819 tests before the change.
- With `item.get_closest_marker(marker) is not None`, all 819 tests are collected.
- `uv run pytest -n 0 tests/invariants/test_hermetic_floor.py -k test_a_default_run_deselects_only_tests_marked_k8s` fails when the bug is present and passes when fixed.

## Existing Tool Considered

Built-in pytest marker inspection via `item.get_closest_marker()`.
