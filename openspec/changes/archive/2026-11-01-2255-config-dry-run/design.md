# Design: Dry-Run Classification for Config, Workspace, OpenSpec, and Docs Commands

## Context & Architecture
Sub-issue #2255 of parent #886 audits commands in `config`, `workspace`, `openspec`, and `docs`.
The dry-run contract defines two classes:
1. `request-plan`: For commands that perform external requests (HTTP, cluster, model, subprocess contacting outside services). A dry run makes zero external requests and returns the planned requests via `render_request_plan` or structured JSON.
2. `no-external-request`: For commands that execute locally without contacting external networks or remote services.
   - For read-only commands without `--dry-run`, `devops --dry-run <command>` executes the command normally through the lazy proxy.
   - For commands modifying local state (`config set`, `workspace add`, `workspace generate`, `workspace remove`), `--dry-run` displays a preview message and skips writes.

## Command Classifications

### 1. Request Plan (1 command)
- `config init`: Decorated with `@dry_run_class("request-plan")`. Accepts `--dry-run` and `--json`. Under dry-run, renders planned execution of `gh auth status` without launching child processes or interactive prompts.

### 2. Local Preview (4 commands)
- `config set`: Decorated with `@dry_run_class("no-external-request")`. Accepts `--dry-run`. Under dry-run, validates inputs and prints `Would set <key> = <value>` or `Would store secret '<key>' in keyring.` without saving to file or keyring.
- `workspace add`: Decorated with `@dry_run_class("no-external-request")`. Accepts `--dry-run`. Under dry-run, validates the path and prints `Would add folder '<path>' to workspace <file>` without writing the workspace file.
- `workspace generate`: Decorated with `@dry_run_class("no-external-request")`. Accepts `--dry-run`. Under dry-run, reads repos and prints `Would generate workspace <file> with <count> folders` without saving.
- `workspace remove`: Decorated with `@dry_run_class("no-external-request")`. Accepts `--dry-run`. Under dry-run, validates folder presence and prints `Would remove folder '<path>' from workspace <file>` without saving.

### 3. Mark Only (17 commands)
Decorated with `@dry_run_class("no-external-request")`:
- `config audit-keys` (remove `--dry-run` and `render_dry_run_result`)
- `config audit-stream`
- `config auth-headless`
- `config env` (alias of `output_env_vars`)
- `config env-vars` (alias of `output_env_vars`)
- `config get`
- `config output` (alias of `output_env_vars`)
- `config show`
- `config unset` (remove `--dry-run` and `render_dry_run_result`)
- `docs check`
- `docs generate` (remove `--dry-run` and `render_dry_run_result`)
- `docs sync-readme` (remove `--dry-run` and `render_dry_run_result`)
- `openspec archive` (remove `--dry-run` and `render_dry_run_result`)
- `openspec check`
- `openspec regenerate` (remove `@dry_run_command` and `--dry-run`)
- `workspace clean` (remove `--dry-run` and `render_dry_run_result`)
- `workspace open`

## Invariant and Test Updates
- Remove the 22 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test suite `tests/commands/test_config_workspace_docs_dry_run.py` covering all 22 commands, verifying plan accuracy, local previews, and network isolation.
- Update `test_config_audit_keys.py`, `test_docs.py`, and `test_openspec_command.py` to reflect the removal of echo-only previews.
