# Proposal: #5843

## Why
Spend tracking classified some cloud backends as local when the gateway was addressed on localhost or private networks. All traffic routed to a `*.local` `api_base` must count as local savings. All requests not routed to a `*.local` `api_base` must count as spend. Local models on the gateway need a `local/` prefix, and cloud models pass through their provider prefixes. Closes #5843.

## What Changes
- Classify `is_local` strictly by `served_by` backend route: only `*.local` domains, loopback addresses, and local transports count as local.
- RFC 1918 private network addresses and internal domain names count as spend.
- Recognize `local/` model prefix as local tier in `_is_local_tier`.
- Add provider-prefixed hosted groups (`gemini/`, `anthropic/`, `openrouter/`) to hosted models and pricing lookup.
- Update telemetry instruments and tests to verify spend and local savings classification.

## Capabilities
- `ai-spend-pricing`: Pricing and spend tracking for AI models and gateway backends.

## Impact
- Accurate spend tracking for gateway requests routed to cloud or VPC backends.
- Proper telemetry metrics for local savings versus cloud spend.

## Feasibility
- Verified with unit tests in `tests/ai/spend/` and telemetry tests in `tests/telemetry/`.
- Validated with existing URL extraction and DNS name utilities.

## Existing Tool Considered
Existing `is_local` implementation in `src/devops_cli/ai/spend/pricing.py` was revised to enforce the route distinction cleanly without extra external dependencies.
