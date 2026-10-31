# Tasks

## 1. Add Invariant Tests

- [x] Add invariant tests in `tests/invariants/test_hermetic_floor.py` for floor resets, fixture uniqueness, dead files, and CI row registration
  - Verification: `uv run pytest tests/invariants/test_hermetic_floor.py`

## 2. Remove Redundant Floor Resets

- [x] Remove autouse fixtures repeating floor resets across test modules
  - Verification: `uv run pytest tests/invariants/test_hermetic_floor.py -k test_test_modules_repeat_no_floor_resets`

## 3. Disambiguate Shared Fixtures

- [x] Rename module-specific `project` and `tree` fixtures across test modules
  - Verification: `uv run pytest tests/invariants/test_hermetic_floor.py -k test_project_and_tree_fixtures_are_distinct`

## 4. Remove Dead Test Files

- [x] Remove the five test files testing test helpers or conftest
  - Verification: `uv run pytest tests/invariants/test_hermetic_floor.py -k test_dead_test_helper_files_are_deleted`

## 5. Register CI Test Settings Row

- [x] Add `test-settings` check spec and subcommand in `devops ci`
  - Verification: `uv run devops ci test-settings`

## 6. Optimize Deep YAML Nesting

- [x] Reduce YAML bracket nesting from 100,000 to 30,000 in `tests/security/test_semgrep_registry.py`
  - Verification: `uv run pytest tests/security/test_semgrep_registry.py -k nested`
