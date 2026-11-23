# Tasks

## 1. Test Support Bounds

- [x] 1.1 Add constants to `tests/support/waits.py` and `tree_guard` to `tests/support/trees.py`
  - Verification: `$ uv run pytest tests/invariants/test_source_tree.py -k test_tree_guard`
- [x] 1.2 Call `tree_guard` in `test_telemetry_instruments.py` and `test_source_tree.py`
  - Verification: `$ uv run pytest tests/invariants/test_source_tree.py -k test_tree_walking_tests_use_tree_guard`
- [x] 1.3 Add 60-second deadline check in `tests/server/test_service_memory.py`
  - Verification: `$ uv run pytest tests/server/test_service_memory.py`

## 2. Quality Gate

- [x] 2.1 Verify OpenSpec validation and local CI gates
  - Verification: `$ uv run devops openspec check`
