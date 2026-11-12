# Tasks

## 1. The constants gate reads only a number that the plan gives to the constant

Kind: fix. Changes: `tests/roadmap/stage/test_roadmap_stage_constants.py`, `src/devops_cli/roadmap/stage/stage_constants.py`.

- [x] 1.1 Write the tests first: the sentences of #4472 (`lines 1790-2000`, `DEFAULT_CI_TEST_SERIAL_MAX_FILES + 1`, `-n 0`, `DEFAULT_CI_TEST_SERIAL_MAX_TESTS: Final[int] = 50` beside `DEFAULT_CI_TEST_NARROWED_WORKERS`) and of #4043 (`at line 266`, a new constant "of 3") give no problem, and a value claim with `is`, `=`, an annotated `=` and `to` gives one. The six texts fail on `origin/main`.
- [x] 1.2 Add `(?!\d)` to `_CANDIDATE_NUMBER`, add `_VALUE_LINK` and `_states_value`, and compare the number in `constant_problems` only when it follows the constant name with `=`, `is` or `to`.
- [x] 1.3 Verify: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py` passes, `uv run devops ci fail-to-pass --base origin/main` shows the six texts fail on the base, and `uv run devops roadmap eval stage --replay` gives the same result on the base and on the change.
