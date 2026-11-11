# Tasks

## 1. Behavior: the table builder skips a module with no declaration

- [x] 1.1 Add the failing tests: `counts_in` does not parse a module whose text does not hold `REGISTRY_COUNTS`, and a module that holds the name only in a comment gives no entry
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_registry.py`
- [x] 1.2 In `counts_in`, return no entry before `ast.parse` when the text does not hold `REGISTRY_COUNTS`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_registry.py tests/roadmap/stage/test_roadmap_stage_split_gates.py`

## 2. Tests: the stage gate tests give their table

- [ ] 2.1 Pass `registry=()` to each call of `check_proposal`, `check_gates` and `gate_arguments` in `tests/roadmap/stage/` that does not test the registry gate, and give the table of the checkout to the test of a new roadmap limit
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## Workflow follow-up

- #4695 makes `registry` a required argument of `check_gates` and `check_proposal`, which takes the place of a `conftest.py` guard against a gate call with no table.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
