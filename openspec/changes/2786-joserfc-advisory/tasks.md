# Tasks

## 1. Lock

- [x] Upgrade `joserfc` to `1.7.7` in `uv.lock`, with no other package changed
  - Verification: `git diff --stat uv.lock` and `uv lock --check`
- [x] Confirm that the audit finds no vulnerability
  - Verification: `uv audit`

## 2. Verification

- [x] Run the full CI quality checks
  - Verification: `uv run devops ci`
