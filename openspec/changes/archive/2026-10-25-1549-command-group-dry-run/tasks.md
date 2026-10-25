# Tasks

## 1. Failing tests

- [x] Add failing test cases for dry-run on command groups with own options in `tests/test_main_dry_run.py`
  - Verification: `uv run devops ci test tests/test_main_dry_run.py`

## 2. Command resolver fix

- [x] Update `_descend_subcommand` in `src/devops_cli/core/command_resolver.py` to parse a copy of `tokens` and return `None` when `parse_tokens` is empty
  - Verification: `uv run devops ci test tests/test_main_dry_run.py`
- [x] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Static checks and OpenSpec validation

- [x] Verify fast checks and OpenSpec gate pass
  - Verification: `uv run devops openspec check`
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
