# Tasks

## 1. Updates

- [x] Update `.python-version` to `3.14.10`
  - Verification: `cat .python-version`
- [x] Update uv to `0.13.6` in `.github/actions/setup-toolchain/action.yml`, `Dockerfile` and `.devcontainer/Dockerfile`
  - Verification: `git diff Dockerfile .devcontainer/Dockerfile .github/actions/setup-toolchain/action.yml`
- [x] Update `.github/ISSUE_TEMPLATE/bug_report.yml` and `tests/test_uv.py`
  - Verification: `git diff`

- [x] Upgrade `authlib` in `uv.lock`
  - Verification: `uv audit` finds no vulnerability

## 2. Verification

- [x] Run full CI quality checks
  - Verification: `uv run devops ci --check`
