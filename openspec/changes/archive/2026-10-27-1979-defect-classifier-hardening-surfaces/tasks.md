# Tasks

## 1. Failing Tests First

- [x] Write failing unit tests in `tests/test_defect_classifier.py` and `tests/test_pr_hardening_report.py` for new hardening surfaces and `AGENTS.md` exclusion
  - Verification: `pytest tests/test_defect_classifier.py` fails on current code

## 2. Implementation

- [x] Update `CONST_HARDENING_SURFACES` in `src/devops_cli/config/constants.py`
  - Verification: `CONST_HARDENING_SURFACES` contains the owning documents and excludes `AGENTS.md`
- [x] Update `match_hardening_surface` and docstrings in `src/devops_cli/github/defect_classifier.py`
  - Verification: `match_hardening_surface` matches owning documents and returns `None` for `AGENTS.md`
- [x] Update `.github/workflows/defect-pr-hardening-audit.yml` declared hardening surfaces list
  - Verification: Workflow surfaces match `CONST_HARDENING_SURFACES` exactly

## 3. Verification & Archival

- [x] Run pytest on modified test suites and full test suite
  - Verification: `uv run pytest tests/test_defect_classifier.py tests/test_pr_hardening_report.py tests/test_workflow_contracts.py` passes
- [x] Run fail-to-pass check against origin/main
  - Verification: `uv run devops ci fail-to-pass --base origin/main` succeeds
- [x] Run static checks and openspec check
  - Verification: `uv run devops openspec check` passes
- [x] Archive OpenSpec change
  - Verification: `uv run devops openspec archive 1979-defect-classifier-hardening-surfaces` succeeds
