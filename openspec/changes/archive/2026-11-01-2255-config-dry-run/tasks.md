# Tasks: Dry-Run Classification for Config, Workspace, OpenSpec, and Docs Commands

## 1. Classify and Implement Commands
- [x] 1.1 Annotate `config init` with `@dry_run_class("request-plan")`, add `--dry-run` and `--json` support, and render planned `gh auth status` request
- [x] 1.2 Annotate `config set` with `@dry_run_class("no-external-request")` and add `--dry-run` local preview
- [x] 1.3 Annotate `workspace add`, `workspace generate`, and `workspace remove` with `@dry_run_class("no-external-request")` and add `--dry-run` local previews
- [x] 1.4 Annotate `config audit-keys`, `config audit-stream`, `config auth-headless`, `config get`, `config output_env_vars` (output, env, env-vars), `config show`, and `config unset` with `@dry_run_class("no-external-request")`, removing echo-only dry-run options and previews
- [x] 1.5 Annotate `docs check`, `docs generate`, and `docs sync-readme` with `@dry_run_class("no-external-request")`, removing echo-only dry-run options and previews
- [x] 1.6 Annotate `openspec archive`, `openspec check`, and `openspec regenerate` with `@dry_run_class("no-external-request")`, removing echo-only dry-run options and previews
- [x] 1.7 Annotate `workspace clean` and `workspace open` with `@dry_run_class("no-external-request")`, removing echo-only dry-run options and previews

## 2. Invariants and Fixtures
- [x] 2.1 Remove the 22 commands from `tests/fixtures/dry_run_gaps.json`
- [x] 2.2 Verify `tests/invariants/test_dry_run_class_ratchet.py` passes

## 3. Test Coverage and Documentation
- [x] 3.1 Create `tests/commands/test_config_workspace_docs_dry_run.py` to test dry runs, tripwires, and plan accuracy across all 22 commands
- [x] 3.2 Update existing tests in `tests/commands/test_config_audit_keys.py`, `tests/docs/test_docs.py`, and `tests/core/test_openspec_command.py`
- [x] 3.3 Synchronize CLI documentation via `uv run devops docs generate --sync-readme`
