# Tasks

## 1. Lock

- [ ] Upgrade `joserfc` to `1.7.7` in `uv.lock`, with no other package changed
  - Verification: `git diff --stat uv.lock` and `uv lock --check`
- [ ] Confirm that the audit finds no vulnerability
  - Verification: `uv audit`

## 2. Verification

- [ ] Run the full CI quality checks
  - Verification: `uv run devops ci`
