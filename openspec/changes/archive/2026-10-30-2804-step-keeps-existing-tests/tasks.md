# Tasks

## 1. The names and the comparison

- [x] Write failing tests in `tests/test_roadmap_implement_test_names.py`: module-level and class tests get qualified names; async tests, tests in `if` and `try` blocks, and nested classes count; a parametrized test is one name; a function inside a function and a non-test function do not count; a file that does not parse gives no names; the lost names of a file that drops, renames or deletes a test; a moved test is lost; a byte order mark does not hide a test; the names are sorted.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_test_names.py`
- [x] Add `src/devops_cli/roadmap/implement_test_names.py` with `defined_tests` and `lost_tests`, built on the standard library `ast`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_test_names.py`

## 2. The exit check

- [x] Write failing tests in `tests/test_roadmap_implement_step_tests_kept.py`: a step that replaces a test file and drops tests stops with a reason that names the file and the tests; a step that adds a test to an existing file ends done; a step that renames a test stops; a step that deletes a test file stops; a step that moves tests to a new file ends done; a new test file and a file with a syntax error do not crash the check; a file with a syntax error after the run is judged by `ruff check` only; the reason names a bounded number of tests and files; the check runs before the verification commands; a fix step gets the check; the extra turn for a static failure cannot remove a test.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_tests_kept.py`
- [x] Change `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py` and `src/devops_cli/config/constants.py`: list the changed test files with git, read the text at the start commit, run the comparison and return the reason.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_tests_kept.py tests/test_roadmap_implement_step.py tests/test_roadmap_implement_step_repair.py tests/test_roadmap_implement_step_ticks.py`

## 3. The instructions and the documentation

- [x] Word the rule in `src/devops_cli/ai/tasks/roadmap_implement_step.md` and in the help of `devops roadmap implement`.
  - Verification: `uv run devops ci test tests/test_ai_task_implement.py tests/test_roadmap_implement_step.py`
- [x] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [x] Archive the change.
  - Verification: `uv run devops openspec archive 2804-step-keeps-existing-tests`
