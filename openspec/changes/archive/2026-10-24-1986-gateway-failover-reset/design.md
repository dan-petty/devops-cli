# Design

## Context

`GatewayRouter` in `src/devops_cli/ai/gateway.py` keeps a route table and a circuit breaker flag in `<data dir>/agent/gateway_state.json`. `devops ai gateway status`, `routes` and `failover` read it. LiteLLM moves the live traffic. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- The status reports each route in failover, also after a healthy probe.
- One command restores the default routes.

**Non-Goals:**

- The saved route table keeps only failover state, so a changed default route reaches each machine that has the file (#2045).
- A probe or a timer that flips a route back.

## Decisions

- **The status reports the routes in failover in a field of their own, and the breaker stays tripped while a route is in failover.** `failover_routes` names the virtual models, and `circuit_breaker_tripped` is true when the probe fails or a route is in failover. So a deliberate failover stays recorded as a trip until a reset. Rejected: keep `circuit_breaker_tripped` as the probe result only. The status then shows no trip while a route is in failover, which is the defect of #1986.
- **A healthy probe does not restore a route.** LiteLLM owns the traffic, so one healthy probe of the gateway does not show that the default backend of a route is healthy. Rejected: restore a route on a healthy probe. The issue and #596 reject it for that reason.
- **A reset restores every route and takes no virtual model.** The issue asks for `failover --reset`, which restores the default routes. A reset with a virtual model is a usage error, so no one reads it as a reset of one route. Rejected: a reset of one route. No consumer needs it, and a per-route reset fits better on the failover state that #2045 keeps.
- **A reset ignores `--simulate`.** The `--simulate/--no-simulate` default is true, and the generated MCP tool sends a true `simulate` as `--simulate`. A reset that obeyed it would write nothing when the tool or a plain `failover --reset` calls it. Rejected: read the source of the `simulate` value from the Click context. The tool always sends the flag, so the source is the command line for each tool call.
- **A reset goes through the same two functions as the load.** `reset_failover` sets the routes to `_build_default_routes()`, clears the breaker, and writes them with `_save_gateway_state`. #2045 changes only those two functions and `_load_gateway_state`: the save keeps only the `failover:*` routes, and the load puts them over the default routes. After that change, the reset writes an empty failover state with no change of its own, and the test of the reset changes only in the content that it expects in the route file.

## Risks / Trade-offs

- [A route table saved before this change holds old routes that are not in failover] → A reset now restores them. #2045 makes the load take them from the defaults.
- [A user resets while LiteLLM still uses a fallback] → The route table then shows the default route while the traffic goes to the fallback. LiteLLM recovers the deployment after its `cooldown_time`, and the route table is a record, not the traffic.
