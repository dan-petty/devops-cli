# Tasks

## 1. Behavior

- [x] 1.1 Write failing unit and real-pytest tests for file-level collection error repair and error phase parsing
  - Verification: `UV_COMPILE_BYTECODE=0 VIRTUAL_ENV= uv run pytest -n 0 tests/ci/test_fail_to_pass.py`
- [x] 1.2 Add `TestCaseOutcome.error_phase` and handle file-level collection errors in `_repaired_and_refused`
  - Verification: `UV_COMPILE_BYTECODE=0 VIRTUAL_ENV= uv run pytest -n 0 tests/ci/test_fail_to_pass.py`

## 2. Documents

- [x] 2.1 Update the Fail-to-Pass Evidence section in `CONTRIBUTING.md` and validate docs
  - Verification: `UV_COMPILE_BYTECODE=0 VIRTUAL_ENV= uv run devops ci --check --only docs`
