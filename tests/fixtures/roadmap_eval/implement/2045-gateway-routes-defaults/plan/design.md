# Design

## Context

`GatewayRouter` in `src/devops_cli/ai/gateway.py` persists routing state to `<data dir>/agent/gateway_state.json`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**

- Persist only failover routes (`backend_type` starting with `failover:`) to the state file.
- Populate all non-failover routes from `_build_default_routes()` on initialization.
- Discard non-failover routes stored in legacy state files during load.

**Non-Goals:**

- Dynamic discovery or updating of upstream backend configurations at runtime.
- Automatic route restoration based on timer or health checks (#1986).

## Decisions

- **Save only failover routes in `_save_gateway_state`.** When persisting routes, filter `routes` by `backend_type.startswith(_FAILOVER_BACKEND_PREFIX)`. Resetting failover writes an empty route list. Rejected alternative: Delete the file on reset. Rejected because `gateway_state.json` also persists `circuit_breaker_active`, which must be retained when not tripped.
- **Overlay failover routes onto default routes in `_load_gateway_state`.** When reading the state file, deserialize valid route entries, select those with `backend_type.startswith(_FAILOVER_BACKEND_PREFIX)`, and map them by `virtual_model`. Construct active routes by taking `_build_default_routes()` and substituting any active failover routes. Rejected alternative: Load and migrate legacy non-failover routes into a new schema version. Rejected because DevOps CLI is pre-1.0 alpha software with no backwards compatibility requirement; non-failover routes are strictly sourced from defaults.

## Risks / Trade-offs

- [A user manually customized non-failover routes in `gateway_state.json`] → These customizations will be ignored in favor of `DEFAULT_GATEWAY_ROUTES`. The CLI does not support manual route editing without failover triggers.
