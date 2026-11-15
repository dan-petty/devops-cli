# Proposal: #5867

## Why
Calls to hosted models through PydanticAI are classified as local savings with the gateway proxy hostname as backend. The gateway endpoint ends in `.local`, which matches the rule for cluster backends. This causes excessive projected local savings in monitoring dashboards. Closes #5867.

## What Changes
- Add `is_gateway_server` to detect when a URL points to the gateway proxy endpoint rather than a serving backend.
- Update `is_local` in `src/devops_cli/ai/spend/pricing.py` to prevent treating the gateway proxy endpoint as a local serving backend.
- Fall through to gateway model routing when `served_by` points to the gateway endpoint.
- In `src/devops_cli/ai/client/factory.py`, set `effective_served_by` to `None` when `served_by` names the gateway proxy endpoint.
- In `src/devops_cli/ai/spend/ledger.py`, do not record the gateway proxy as the backend name on emitted telemetry.
- Add unit tests for gateway endpoint detection and spend classification.

## Capabilities
- `ai-spend-pricing`: Pricing and spend classification for gateway requests and proxy endpoints.

## Impact
- Accurate classification of spend versus local savings for PydanticAI requests through the gateway.
- Prevents hosted model calls from inflating local savings metrics in Prometheus and Grafana.

## Feasibility
- Verified reproduction with command in issue #5867.
- Verified with unit tests in `tests/ai/spend/` and `tests/ai/client/`.

## Existing Tool Considered
Existing `is_local` implementation in `src/devops_cli/ai/spend/pricing.py` was revised to ignore gateway proxy endpoints when evaluating serving backend routes.
