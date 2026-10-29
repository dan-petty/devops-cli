# Tasks

## 1. Fix release pull request merge step

- [x] Update `tests/test_workflow_contracts.py` to assert the updated contract
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py`
- [x] Update `.github/workflows/release.yml` to pass raw output and parse with `jq`
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py`
- [x] Update `openspec/specs/release-urgent-merge/spec.md`
  - Verification: `uv run devops openspec check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2616-release-pr-merge-empty`
