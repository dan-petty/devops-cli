# Tasks

## 1. Tests First

- [x] 1.1 Add test proving exported dry-run variable survives command with own dry-run flag
  - Verification: `$ uv run pytest tests/commands/test_entry_point.py`
- [x] 1.2 Add test proving early-stop options record dry-run invocation
  - Verification: `$ uv run pytest tests/commands/test_entry_point.py`

## 2. Refactor Entry Point

- [x] 2.1 Remove `set_dry_run` call and import from `src/devops_cli/entry.py`
  - Verification: `$ uv run pytest tests/commands/test_entry_point.py`
- [x] 2.2 Add invariant test confirming `entry.py` does not import `set_dry_run`
  - Verification: `$ uv run pytest tests/commands/test_entry_point.py`

## 3. Quality Gates

- [x] 3.1 Run OpenSpec check
  - Verification: `$ uv run devops openspec check`
- [x] 3.2 Run full CI suite
  - Verification: `$ uv run devops ci`
