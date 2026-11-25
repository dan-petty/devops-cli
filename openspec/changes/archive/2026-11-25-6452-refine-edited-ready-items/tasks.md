# Tasks

## 1. Behavior

- [x] 1.1 Write failing selection and explain tests for edited or commented `Ready` items
  - Verification: `UV_COMPILE_BYTECODE=0 VIRTUAL_ENV= uv run pytest -n 0 tests/roadmap/refine/test_roadmap_refine_selection.py tests/roadmap/test_roadmap_explain.py`
- [x] 1.2 Update `_refinable`, `_select_round`, `refine_due_reason`, `explain.py`, `messages.py`, and test fixtures
  - Verification: `UV_COMPILE_BYTECODE=0 VIRTUAL_ENV= uv run pytest -n 0 tests/roadmap/refine/ tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_explain_command.py`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/refine.md` and regenerate CLI reference messages
  - Verification: `UV_COMPILE_BYTECODE=0 VIRTUAL_ENV= uv run devops docs generate && UV_COMPILE_BYTECODE=0 VIRTUAL_ENV= uv run devops ci --check --no-cache --skip test,outdated`
