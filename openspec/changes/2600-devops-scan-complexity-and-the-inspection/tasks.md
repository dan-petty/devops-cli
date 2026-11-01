# Tasks

## 1. State why the port stays

Reads: `src/devops_cli/core/code_metrics.py`. Changes: `src/devops_cli/core/code_metrics.py`.

- [ ] 1.1 Run the tests that hold the port and its two readers, and check that they pass before the edit. They are the check for this group, because no behavior changes
  - Verification: `uv run devops ci test tests/core/test_code_metrics.py tests/core/test_scan_complexity.py tests/ai/test_ai_inspection.py tests/security/test_review_ruff_mypy_evidence.py`
- [ ] 1.2 Add a paragraph to the module docstring of `src/devops_cli/core/code_metrics.py`, after the first paragraph. It says that the module does not call Ruff: Ruff is a development dependency, and `ruff check` gives the figure only in a message string, only for a function above `max-complexity`. It says that `tests/core/test_code_metrics.py` holds 12 figures that were taken from `ruff check --select C901` with `max-complexity=0`, and that the test does not run Ruff, so a later change of Ruff counting does not fail it
  - Verification: `git grep -n "development dependency" src/devops_cli/core/code_metrics.py` prints the new line, and the command of task 1.1 passes again

## 2. Archive

- [ ] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 2600-devops-scan-complexity-and-the-inspection`
