# Tasks

## 1. The gate writes no XML report, and the clean-up keeps the combined data

- [x] Add failing tests: the test row's command holds no `--cov-report=xml`; the clean-up keeps a two-hour-old `.data/.coverage` and removes the worker files; the `Changed-Line Coverage` step runs `uv run coverage xml` before diff-cover
  - Verification: `uv run devops ci test tests/test_ci.py`
- [x] Remove `--cov-report=xml` from `_resolve_pytest_cmd`, make the clean-up glob `.coverage.*`, and delete the removal of a root `coverage.xml` that nothing writes
  - Verification: `uv run devops ci test tests/test_ci.py tests/test_ci_dry_run.py`
- [x] Run `uv run coverage xml -q` in the `Changed-Line Coverage` step before diff-cover
  - Verification: `uv run devops ci test tests/test_ci.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1743-coverage-xml-in-ci`

## Workflow follow-up

- #2373 measures the rest of the serial end of the test row (the combine step and the `term-missing` report) and decides whether the runner keeps `term-missing`.
- #1325 owns the `PYTEST_CURRENT_TEST` checks in `_clean_coverage_artifacts`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
