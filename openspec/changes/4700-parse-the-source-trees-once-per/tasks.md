# Tasks

## 1. Refactor: parse each file once (test-only edits)

- [x] 1.1 Read `parsed_source_trees` in the gauge, metric and emit checks of `tests/telemetry/test_telemetry_instruments.py`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py`
- [x] 1.2 Call `parse_python_file` in the walks of `test_source_tree.py`, `test_roadmap_runner_tools.py`, `test_edge_fixtures.py`, `test_github_session.py`, `test_ai_spend_pricing.py` and `test_test_selection.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_source_tree.py tests/roadmap/test_roadmap_runner_tools.py tests/scaffold/test_edge_fixtures.py tests/github/test_github_session.py tests/ai/spend/test_ai_spend_pricing.py tests/commands/test_test_selection.py`
- [x] 1.3 Read the cache in the fallbacks of `tests/gate/tree_checks/module_independence.py` and `tests/gate/swallowed_failures.py`
  - Verification: `$ uv run devops ci --only test-tree,swallowed-failures`

## 2. Move and delete (refactor that keeps behavior)

- [x] 2.1 Move `test_project_and_tree_fixtures_are_distinct` from `tests/invariants/test_hermetic_floor.py` to `tests/gate/tree_checks/fixture_names.py`, with a probe check of its logic
  - Verification: `$ uv run devops ci --only test-tree`
- [x] 2.2 Delete `test_every_import_of_a_roadmap_module_names_a_module_that_exists`, `_roadmap_import_problems`, `_roadmap_path` and `_ROADMAP_DOTTED`
  - Verification: `$ ! git grep -n -e _roadmap_import_problems -e test_every_import_of_a_roadmap_module -- tests/`
