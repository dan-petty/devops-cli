# Design

## Context
See `proposal.md` for motivation.
Devops-cli enforces the owner's dry-run rule (#412) via `@dry_run_class`.
The 9 Valkey commands communicate with external Valkey instances via TCP sockets through `ValkeyClient`.
The 7 Vault commands communicate with external HashiCorp Vault HTTP API endpoints via `httpx2` through `VaultSecretBroker` and `vault_http.vault_request`.
The `vault audit` command inspects local in-process session records and makes no external network calls.

In dry-run mode, commands that make external requests must not open sockets or issue network requests. Instead, they must generate an ordered list of `PlannedRequest` items and render them with `render_request_plan`.

## Goals / Non-Goals

**Goals:**
- Implement plan generation functions in `devops_cli.valkey.valkey_plans` and `devops_cli.security.vault_plans`.
- Decorate 9 Valkey commands with `@dry_run_class("request-plan")`.
- Decorate 7 Vault commands with `@dry_run_class("request-plan")`.
- Decorate `vault audit` with `@dry_run_class("no-external-request")`.
- Add `--dry-run` option to commands that lack it (`valkey cli`, `valkey get`, `valkey info`, `valkey keys`, `valkey ping`, `valkey stats`).
- Ensure each command respects `--dry-run` and global `devops --dry-run <cmd>`.
- In dry-run mode, make zero network, socket, or external process calls.
- Render tabular request plans with `render_request_plan`.
- Remove legacy echo-only previews (`render_dry_run_result` and `@dry_run_command`) with no shim.
- Remove all 17 commands from `tests/fixtures/dry_run_gaps.json`.

**Non-Goals:**
- Modifying behavior in non-dry-run mode.
- Adding backwards-compatibility shims for legacy echo-only preview output.

## Decisions

### 1. Dedicated plan modules (`valkey_plans.py` and `vault_plans.py`)
- **Decision**: Put plan builders in `src/devops_cli/valkey/valkey_plans.py` and `src/devops_cli/security/vault_plans.py`.
- **Rationale**: Isolates request planning and argument generation, keeping command definitions lightweight and preventing cyclical imports. Follows patterns established across the codebase (`cloudflare_plans.py`, `argo_plans.py`, `tf_plans.py`).
- **Alternatives considered**:
  - *Inline plan generation directly in CLI callback bodies*: Rejected because it increases command cyclomatic complexity beyond the project ceiling (10) and prevents unit testing plans in isolation.

### 2. Protocol and HTTP Request Planning
- **Decision**:
  - For Valkey commands, represent operations using `PlannedRequest(method="valkey", target="<COMMAND> <ARGS>")`.
  - For Vault commands, represent planned HTTP calls with `method="GET"|"POST"`, `target=vault_url(...)`, and `stdin` holding the serialized JSON payload when applicable, with secrets masked by placeholders (`<placeholder>`).
- **Rationale**: Accurately describes what would execute against Valkey and Vault instances while adhering to `PlannedRequest` conventions.

## Risks / Trade-offs
- [Cyclomatic complexity in command functions] → Keep dry-run handling concise and delegate plan creation to dedicated helper functions to stay within cyclomatic complexity limits (<=10).
- [Socket leakage in tests] → Use socket and HTTP client monkeypatch guards to guarantee zero external calls are made during dry runs.
