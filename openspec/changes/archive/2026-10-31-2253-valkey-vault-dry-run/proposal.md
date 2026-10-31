# Proposal

## Why
Issue #2253 addresses the dry-run rule (#412) for Valkey and Vault commands. The rule states that a dry run makes no external requests and returns the planned requests that the real run makes. Currently, 16 Valkey and Vault commands make external network requests or print an echo-only preview during a dry run, and 1 Vault command makes no external requests and needs the `no-external-request` classification.

## What Changes
- Classify 9 Valkey commands with `@dry_run_class("request-plan")`:
  - `valkey backup`
  - `valkey cli`
  - `valkey flush`
  - `valkey get`
  - `valkey info`
  - `valkey keys`
  - `valkey ping`
  - `valkey set`
  - `valkey stats`
- Classify 7 Vault commands with `@dry_run_class("request-plan")`:
  - `vault get`
  - `vault leases`
  - `vault login`
  - `vault logout`
  - `vault set`
  - `vault status`
  - `vault sync`
- Classify 1 Vault command with `@dry_run_class("no-external-request")`:
  - `vault audit`
- Add `--dry-run` option to commands where it is missing (`valkey cli`, `valkey get`, `valkey info`, `valkey keys`, `valkey ping`, `valkey stats`).
- Provide request plan builders in `devops_cli.valkey.valkey_plans` and `devops_cli.security.vault_plans`.
- In dry-run mode, make zero network, socket, or subprocess calls.
- Render planned requests with `render_request_plan` for tabular display.
- Remove legacy echo-only previews (`render_dry_run_result` and `@dry_run_command`) with no backward-compatibility shim.
- Remove all 17 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test suites verifying classifications, planned requests, and zero external calls.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `command-dry-run-class`: Add requirements and scenarios specifying request-plan behavior and zero external calls for the 16 Valkey and Vault commands, and normal execution for `vault audit`.

## Impact
- Command interfaces: Valkey and Vault CLI commands gain standard request planning in dry-run mode.
- Test suite: `tests/fixtures/dry_run_gaps.json` gap count decreases by 17. Tests verify zero external calls under dry run.
- Documentation: Valkey and Vault command documentation reflects standard request-plan dry-run behavior.

## Feasibility
Confirmed against repository code and library sources:
- Valkey commands interact with Valkey servers through `ValkeyClient` over network sockets.
- Vault commands interact with HashiCorp Vault HTTP endpoints through `vault_request` and `httpx2`.
- `vault audit` accesses local in-memory session audit logs only and performs no network operations.
- `PlannedRequest` and `render_request_plan` in `devops_cli.dry_run.requests` provide standard request planning.
- The 17 commands match the 17 Valkey and Vault entries in `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Existing Tool Considered
The change uses internal mechanisms `PlannedRequest`, `render_request_plan`, and `@dry_run_class` introduced in #741 and sub-issue 00 (#886). It removes legacy echo-only previews with no backward-compatibility shim.
