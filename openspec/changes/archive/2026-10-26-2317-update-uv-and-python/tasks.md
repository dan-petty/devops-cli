# Tasks

## 1. Updates

- [x] Update `.python-version` to `3.14.9`
  - Verification: `cat .python-version`
- [x] Update `version` in `.github/actions/setup-toolchain/action.yml` to `0.13.5`
  - Verification: `git diff .github/actions/setup-toolchain/action.yml`
- [x] Update `.github/ISSUE_TEMPLATE/bug_report.yml` and `tests/test_uv.py`
  - Verification: `git diff`

## 2. Verification

- [x] Run full CI quality checks
  - Verification: `uv run devops ci --check`
