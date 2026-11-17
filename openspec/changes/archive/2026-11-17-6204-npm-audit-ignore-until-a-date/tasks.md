# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for the ignore file, the expiry, the lockfile scope and the gate row
  - Verification: `$ uv run pytest tests/commands/test_dependency_audit.py -q`
- [x] 1.2 Read `.npm-audit-ignore.yaml` in `devops ci audit` and the gate's `audit` row
  - Verification: `$ uv run pytest tests/commands/test_dependency_audit.py -q`
- [x] 1.3 Add the entry for GHSA-fc5q-39xc-vjpf, tracked by #6202
  - Verification: `$ uv run devops ci audit`

## 2. Documents

- [x] 2.1 Name the file in SECURITY.md and docs/ROUTINE_TASKS.md
  - Verification: `$ uv run devops ci docs`
