# Proposal

## Why
Issue #2252 addresses the dry-run rule (#412) for Cloudflare commands. The rule states that a dry run makes no external requests and returns the planned requests that the real run makes. Currently, 10 Cloudflare commands make external HTTP requests or print an echo-only preview during a dry run.

## What Changes
- Classify all 10 Cloudflare commands with `@dry_run_class("request-plan")`:
  - `cloudflare status`
  - `cloudflare service-status`
  - `cloudflare dns list`
  - `cloudflare dns sync`
  - `cloudflare dns delete`
  - `cloudflare tunnel routes`
  - `cloudflare tunnel sync`
  - `cloudflare access status`
  - `cloudflare access sync`
  - `cloudflare access policies`
- Add `--dry-run` to the commands where it is missing.
- Provide request plan builders in `devops_cli.cloudflare.cloudflare_plans`.
- In dry-run mode, make zero HTTP, socket, or external process calls.
- Render planned requests with `render_request_plan` for tabular display.
- Return structured output with `dry_run: true` and planned requests when `--format json` or `--json` is selected.
- Remove legacy echo-only previews and simulated outputs with no backward compatibility shim.
- Remove all 10 Cloudflare commands from `tests/fixtures/dry_run_gaps.json`.
- Add test suites verifying classifications, planned requests, and zero external calls.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `command-dry-run-class`: Add requirements and scenarios specifying request-plan behavior and zero external calls for the 10 Cloudflare commands.

## Impact
- Command interfaces: Cloudflare CLI commands gain standard request planning in dry-run mode.
- Test suite: `tests/fixtures/dry_run_gaps.json` gap count decreases by 10. Tests verify zero external calls under dry run.
- Documentation: Cloudflare command documentation reflects standard request-plan dry-run behavior.

## Feasibility
Confirmed against repository code and library sources:
- All 10 Cloudflare commands make HTTP calls via `httpx2` through `CloudflareClient` or statuspage client functions.
- `PlannedRequest` and `render_request_plan` in `devops_cli.dry_run.requests` provide standard request planning.
- The 10 commands match the 10 Cloudflare entries in `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Existing Tool Considered
The change uses internal mechanisms `PlannedRequest`, `render_request_plan`, and `@dry_run_class` introduced in #741 and sub-issue 00 (#886). It removes legacy echo-only previews with no backward-compatibility shim.
