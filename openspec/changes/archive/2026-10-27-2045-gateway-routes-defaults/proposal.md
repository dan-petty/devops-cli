# Proposal

## Why

Issue #2045: the gateway router loads a saved route table from `<data dir>/agent/gateway_state.json` in place of `DEFAULT_GATEWAY_ROUTES`. No command refreshes that table when default routes change in the code. A change to default routes, such as #1969's move to served models, never reaches a machine that already holds a saved state file.

## What Changes

- `_save_gateway_state` keeps only failover routes (routes whose `backend_type` begins with `failover:`) in `gateway_state.json`. Routes that are not in failover are omitted from the saved file.
- `_load_gateway_state` takes every route from `DEFAULT_GATEWAY_ROUTES` and overlays only the saved failover routes (`failover:*`). Any non-failover route present in an existing saved state file is ignored.
- A failover reset writes an empty list of failover routes and clears the circuit breaker.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: ADDED requirement that a saved route table keeps only failover state, and MODIFIED requirement for failover reset state persistence.

## Impact

- Code: `src/devops_cli/ai/gateway.py` (`_load_gateway_state` and `_save_gateway_state`).
- Tests: `tests/test_ai_gateway.py`.
- Documents: none. CLI surface, options, and commands remain unchanged.

## Feasibility

- Confirmed by inspecting `src/devops_cli/ai/gateway.py` at commit 69928b05: `_save_gateway_state` writes `[r.model_dump() for r in routes]`, saving all active routes. `_load_gateway_state` returns `[GatewayRoute.model_validate(r) for r in raw_routes]` directly, replacing `DEFAULT_GATEWAY_ROUTES`.
- Confirmed by `openspec/changes/archive/2026-10-24-1986-gateway-failover-reset/design.md`: #1986 deferred this fix to #2045, stating that the save should keep only `failover:*` routes and the load should overlay them on default routes.
- Confirmed with tests: an existing test file written with old routes causes `GatewayRouter` to use those old routes rather than `DEFAULT_GATEWAY_ROUTES`.

## Existing Tool Considered

LiteLLM routes live traffic. The CLI gateway router manages local state and model metadata for devops commands. We retain the existing `GatewayRouter` implementation and delete the code that serializes default routes into persistent storage. No new tool or external library is needed.
