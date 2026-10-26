# Design

## Context

Cloudflare Radar tracks domain information, rankings, and traffic categories.
DevOps CLI uses Radar threat intelligence to audit domain targets referenced in source files under review and in threat-intel tool queries.
Issue #1429 reports that `CloudflareRadarClient` used an undocumented, unauthenticated endpoint at `radar.cloudflare.com/api/v1/intel`.
The previous code also returned synthetic success text ("Domain verified in public DNS registry" and "Verified domain reference") when queries failed or errored.
These synthetic strings caused review reports and threat intelligence tools to mark failed lookups as safe.

## Architecture

### 1. Documented Endpoint and Authentication

`CloudflareRadarClient` targets `https://api.cloudflare.com/client/v4/radar/ranking/domain/{domain}`.
It resolves the Cloudflare API token through `get_cloudflare_api_token(settings)`.
If a token is available, the client sends `Authorization: Bearer <token>`.
If no token is configured:
- The client sends no HTTP request.
- The lookup returns outcome `unavailable` with reason explanation.

### 2. Explicit Outcomes on NetworkReputationRecord

`NetworkReputationRecord` in `src/devops_cli/models/vulnerability.py` defines an `outcome` field:
- `ok`: Successful query with parsed fields (tags, ranking).
- `unavailable`: Token not configured, or HTTP 429 rate limit exceeded.
- `failed`: HTTP 403 forbidden, HTTP 500 server error, non-200 responses, or network connection errors.

Summaries and tags come only from fields of successful replies.
When lookups fail or are unavailable, tags remain empty.

### 3. Review and Threat Intel Presentation

The review pipeline (`_audit_file_network_references`) checks `rep.outcome`.
If `rep.outcome` is `unavailable` or `failed`:
- The security status is set to `Unverified`.
- The markdown output displays `Unverified` without "Safe" or "verified" text.

The threat-intel tool (`_radar_reply` in `src/devops_cli/ai/tools/builtin_tools.py`):
- Displays `Status: Unverified (<outcome>)` when the lookup is not `ok`.
- Lists `Threat Categories: None` rather than synthetic classifications.

### 4. Cache Tiering

- Unasked targets (reserved example domains, local networks) return static records without sending requests.
- Only successful records (`outcome == "ok"`) are written to Valkey L2 cache.
- In-memory L1 cache caches results within the process to prevent duplicate queries during a single run.

### 5. HTTP Edge Testing

Tests use `httpx2.MockTransport` at the HTTP library edge.
No test patches a `devops_cli` module, class, or function name.

## Alternatives Considered and Rejected

- **Use the `cloudflare` Python SDK**:
  The official `cloudflare` SDK (version 5.9.0) depends on `httpx`, not `httpx2`.
  It cannot integrate with the egress-checked client factory required by the project.
  Direct use of `httpx2` against the documented REST API v4 satisfies all security and operational requirements.

- **Keep the undocumented endpoint as fallback**:
  Cloudflare's `radar.cloudflare.com/api/v1/intel` endpoint is not documented for public API consumption.
  It is unauthenticated and subject to unexpected removal or breaking changes.
  AGENTS.md requires using documented upstream interfaces.

- **Default failed lookups to safe or verified**:
  Returning "Domain verified in public DNS registry" on HTTP errors or connection timeouts masks scan failures.
  AGENTS.md forbids synthetic assessments.
  Errors must clearly report as unverified.
