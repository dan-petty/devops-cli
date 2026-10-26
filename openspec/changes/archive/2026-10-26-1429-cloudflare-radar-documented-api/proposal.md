# Proposal

## Why

In #1429, `CloudflareRadarClient` uses an undocumented endpoint `https://radar.cloudflare.com/api/v1/intel/domain/{target}` with no credentials.
Cloudflare documents the Radar API at `https://api.cloudflare.com/client/v4/radar/` and requires an API token.
When a lookup fails with an HTTP error or connection failure, the current code generates synthetic success text.
The client records "Domain verified in public DNS registry" or "Verified domain reference".
The threat-intel tool and review pipeline then show the failed domain as safe and verified.
AGENTS.md forbids synthetic assessments.

This change fits one pull request.

## What Changes

- Query the documented Cloudflare Radar endpoint at `https://api.cloudflare.com/client/v4/radar/ranking/domain/{domain}`.
- Resolve the Cloudflare API token through `get_cloudflare_api_token(settings)`.
- Send the `Authorization: Bearer <token>` header with each query.
- When no token is configured, send no request and return outcome `unavailable`.
- Record an explicit `outcome` (`ok`, `unavailable`, or `failed`) on each `NetworkReputationRecord`.
- On HTTP 429, set outcome `unavailable`.
- On HTTP 403, 500, or network connection errors, set outcome `failed`.
- Derive summaries and tags only from fields of successful replies.
- Update the review pipeline and threat-intel tool to show unavailable and failed lookups as unverified, never as safe or verified.
- Remove deprecated strings `radar.cloudflare.com/api`, `Verified domain reference`, and `verified in public DNS`.
- Write offline tests using `httpx2.MockTransport` at the HTTP edge without patching `devops_cli` names.

This change alters internal threat intelligence lookup endpoints, status models, and review display text.
It does not change CLI options, commands, or configuration files.
The change sets `skip_specs: true` in `.openspec.yaml`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/models/vulnerability.py`: adds `outcome` field to `NetworkReputationRecord`.
- `src/devops_cli/security/vulnerability_lookup.py`: updates `CloudflareRadarClient` endpoint, authentication, and error outcomes.
- `src/devops_cli/ai/tools/builtin_tools.py`: formats unverified lookup replies for unavailable and failed domain lookups.
- `src/devops_cli/ai/review/pipeline.py`: displays unverified security status for unavailable and failed network targets.
- `tests/test_vulnerability_lookup.py`: tests documented Radar endpoints, token handling, outcomes, and edge doubles.
- `tests/test_security_threat_intel.py`: updates cache tests for documented endpoints and error outcomes.

## Feasibility

- Confirmed against Cloudflare Radar documentation (`developers.cloudflare.com/radar/`) that Radar API v4 requires `Authorization: Bearer <token>`.
- Confirmed that `GET /radar/ranking/domain/{domain}` under `https://api.cloudflare.com/client/v4` provides domain ranking and categories.
- Confirmed with `src/devops_cli/config/settings.py:1433` that `get_cloudflare_api_token(settings)` resolves the token from settings or environment variables.
- Confirmed that `src/devops_cli/security/vulnerability_lookup.py:456` previously targeted `https://radar.cloudflare.com/api/v1/intel`.
- Confirmed that lines 522 and 531 previously set synthetic "verified" summary strings on errors.
- Confirmed that `src/devops_cli/ai/review/pipeline.py:3135` previously assigned "✓ Safe / Low Risk" to failed lookups.

## Existing Tool Considered

Cloudflare provides the `cloudflare` Python SDK (version 5.9.0).
The SDK uses `httpx` rather than `httpx2` and cannot accept the project egress-checked client.
Using `httpx2` directly with `https://api.cloudflare.com/client/v4/radar/ranking/domain/{domain}` meets all requirements with minimal overhead.
This change deletes the internal undocumented URL `https://radar.cloudflare.com/api/v1/intel`, and the synthetic fallback strings "Domain verified in public DNS registry" and "Verified domain reference".
