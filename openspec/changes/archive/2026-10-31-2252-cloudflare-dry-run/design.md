# Design

## Context
See `proposal.md` for motivation.
Devops-cli enforces the owner's dry-run rule (#412) via `@dry_run_class`.
The 10 Cloudflare commands communicate with external HTTP APIs:
- Cloudflare REST API v4 (`https://api.cloudflare.com/client/v4`) via `CloudflareClient`.
- Atlassian Statuspage summary endpoint (`https://www.cloudflarestatus.com/api/v2/summary.json`) via `fetch_cloudflare_status`.

The 10 commands must not make network requests or open sockets in dry-run mode. Instead, they must generate an ordered list of `PlannedRequest` items and render them with `render_request_plan` or emit structured output for JSON/YAML formats.

## Goals / Non-Goals

**Goals:**
- Implement plan generation functions in `devops_cli.cloudflare.cloudflare_plans`.
- Decorate all 10 Cloudflare commands with `@dry_run_class("request-plan")`.
- Add `--dry-run` option to commands that lack it (`status`, `service-status`, `dns list`, `tunnel routes`, `access status`, `access policies`).
- Ensure each command respects `--dry-run` and global `devops --dry-run <cmd>`.
- In dry-run mode, make zero HTTP, socket, or external process calls.
- Render tabular request plans with `render_request_plan` and structured output when JSON/YAML formatting is selected.
- Remove legacy echo-only previews (`_preview_dns_sync`, `_preview_tunnel_sync`, `_preview_access_sync`, etc.) with no shim.
- Remove all 10 Cloudflare commands from `tests/fixtures/dry_run_gaps.json`.

**Non-Goals:**
- Modifying behavior in non-dry-run mode.
- Adding backwards-compatibility shims for legacy echo-only preview output.

## Decisions

### 1. Dedicated plan module (`cloudflare_plans.py`)
- **Decision**: Put plan builders in `src/devops_cli/cloudflare/cloudflare_plans.py`.
- **Rationale**: Isolates request planning and argument generation, keeping command definitions lightweight and preventing cyclical imports. Follows patterns established in `docker_plans.py`, `sandbox_plans.py`, `tf_plans.py`, and `argo_plans.py`.
- **Alternatives considered**:
  - *Inline plan generation directly in CLI callback bodies*: Rejected because it increases command cyclomatic complexity beyond the project ceiling (10) and prevents unit testing plans in isolation.

### 2. Matching Cloudflare REST API endpoint structure
- **Decision**: Represent planned HTTP calls with `method="GET"|"POST"|"PUT"|"DELETE"`, `target=url`, and `stdin` holding the serialized JSON payload when applicable.
- **Rationale**: Accurately describes what would execute against the Cloudflare API while adhering to `PlannedRequest`.

## Risks / Trade-offs
- [Cyclomatic complexity in command functions] → Extract dry-run dispatch to concise helper functions where needed to adhere to the cyclomatic complexity ceiling (<=10).
- [Socket leakage in tests] → Use session socket guards and monkeypatch HTTP clients to guarantee zero external calls are made during dry runs.
