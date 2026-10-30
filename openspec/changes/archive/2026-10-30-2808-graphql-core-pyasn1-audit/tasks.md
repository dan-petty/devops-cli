# Tasks

## 1. Lock

- [x] Upgrade `pyasn1` to `0.6.5` in `uv.lock`, and raise the pin of `graphql-core` to `==3.3.1` in `pyproject.toml` and `uv.lock`
  - Verification: `git diff --stat pyproject.toml uv.lock` and `uv lock --check`
- [x] Confirm that the audit finds no vulnerability
  - Verification: `uv audit`

## 2. Verification

- [x] Run the full CI quality checks
  - Verification: `uv run devops ci`
