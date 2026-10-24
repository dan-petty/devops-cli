# Tasks

## 1. The status reports the routes in failover

- [x] 1.1 Write `test_a_healthy_probe_keeps_a_failover_route_and_the_status_reports_it` and `test_status_reports_the_routes_in_failover` in `tests/test_ai_gateway.py`, and verify that `uv run devops ci test tests/test_ai_gateway.py` fails on the base because `GatewayStatus` has no `failover_routes`
- [x] 1.2 Add `GatewayStatus.failover_routes`, keep the circuit breaker tripped while a route is in failover, and make the `status` table name the routes in failover and the reset, and verify that `uv run devops ci test tests/test_ai_gateway.py` passes

## 2. A reset restores the default routes

- [x] 2.1 Write `test_failover_reset_restores_the_default_routes`, `test_failover_reset_command` and `test_fastmcp_gateway_failover_resets_the_routes` in `tests/test_ai_gateway.py`, and verify that `uv run devops ci test tests/test_ai_gateway.py` fails on the base because `GatewayRouter` has no `reset_failover` and the command has no `--reset`
- [x] 2.2 Add `GatewayRouter.reset_failover` and `devops ai gateway failover --reset`, which takes no virtual model and ignores `--simulate`, and verify that `uv run devops ci test tests/test_ai_gateway.py tests/test_fastmcp_contracts.py tests/test_mcp.py` passes
- [x] 2.3 Regenerate the command and MCP tool documents with `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- The saved route table keeps only failover state, so a changed default route reaches each machine that has the file: moved to #2045. The reset goes through `_build_default_routes` and `_save_gateway_state`, which that item changes (design.md).
- The help of `devops ai failover` says that `devops ai gateway failover` reroutes requests, but LiteLLM's `router_settings.fallbacks` move the traffic and the gateway failover records a route: moved to #2079.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
