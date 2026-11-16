# Tasks

## 1. Behavior

- [x] 1.1 Write failing invariant test in `tests/invariants/test_hermetic_floor.py`
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_hermetic_floor.py -k test_a_default_run_deselects_only_tests_marked_k8s`
- [x] 1.2 Update `_deselect_by_marker` in `tests/conftest.py` to use `item.get_closest_marker()`
  - Verification: `$ uv run pytest -n 0 --co -q tests/k8s/`

## 2. Verification

- [x] 2.1 Run hermetic floor invariant tests
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_hermetic_floor.py`
- [x] 2.2 Run static and format checks
  - Verification: `$ uv run devops ci typecheck && uv run ruff check && uv run ruff format --check`
