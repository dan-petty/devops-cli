# Proposal

## Why

Issue #1986: `devops ai gateway failover --no-simulate` writes a `failover:*` route to the route table in `<data dir>/agent/gateway_state.json`, and no command restores the default route. A healthy probe clears the circuit breaker flag but keeps the failover route. So `devops ai gateway status` shows a healthy gateway with no tripped breaker while a route still points at its failover backend.

## What Changes

- `devops ai gateway status` names each virtual model whose route is a `failover:*` route, in the new field `failover_routes` of its JSON and in a `Failover routes:` line of its table, which also names the reset. The circuit breaker stays tripped while a route is in failover, also after a healthy probe. A healthy probe does not change a `failover:*` route.
- `devops ai gateway failover --reset` restores the default route of every virtual model and clears the circuit breaker. A reset takes no virtual model. `--simulate` and `--force` apply only to a failover, so a reset always writes the route table. The MCP tool `ai_gateway_failover` comes from the command, so it gets the parameter `reset`, and its `virtual_model` is optional.
- Failback stays explicit. LiteLLM's `router_settings.fallbacks` move the live traffic, so the route table does not flip back on one healthy probe. A deliberate failover stays recorded until a reset.
- The status, the option and the tool are observable, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: ADDED requirements for the failover report of the status and for the reset.

## Impact

- Code: `src/devops_cli/ai/gateway.py` (`GatewayStatus.failover_routes`, `GatewayRouter.probe_gateway` and the new `GatewayRouter.reset_failover`) and `src/devops_cli/commands/ai_gateway.py` (`status` and `failover`).
- Tests: `tests/test_ai_gateway.py`.
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md` and `docs/MCP_TOOLS.md`, from `devops docs generate --sync-readme`.

## Feasibility

- At the base commit 0a2bfe1f, `trigger_failover` in `src/devops_cli/ai/gateway.py` writes `backend_type=f"failover:{b_type}"`, and `probe_gateway` sets `_circuit_breaker_active = not is_ok` and saves the routes as they are. `failover_cmd` in `src/devops_cli/commands/ai_gateway.py` has `--simulate` and `--force` and no reset.
- Only `devops ai gateway status`, `routes` and `failover` read the route table: `GatewayRouter` has no caller in `src/devops_cli` outside `commands/ai_gateway.py`, and the other commands there use only its gateway URL and its backend probe. `build_pydantic_cascade_model` reads `MODEL_FAILOVER_PAIRS`, not the route table.
- LiteLLM's `router_settings.fallbacks` in `k8s/llm/gateway/config.yaml` move the live traffic, so the change builds no failover engine. It makes the route table and its report correct.
- The MCP tool `ai_gateway_failover` is generated from the command (`CONST_MCP_EXPOSURE_TABLE`, `src/devops_cli/ai/mcp/generator.py`), and the generator sends a true `simulate` as `--simulate`. So a reset that obeyed `--simulate` would never write when the tool calls it. That is why a reset ignores `--simulate`.
- On the base commit, the five new tests in `tests/test_ai_gateway.py` failed: `GatewayStatus` had no `failover_routes`, `GatewayRouter` had no `reset_failover`, and the command and the tool had no reset.

## Existing Tool Considered

LiteLLM's router is the tool that moves the live traffic, through `router_settings.fallbacks`, and it already recovers a deployment after its `cooldown_time`. Nothing is built: the change reports and resets the route table that the CLI already keeps, through its existing `_build_default_routes` and `_save_gateway_state`. It deletes the `failover:` literal in `trigger_failover`, which now uses the one prefix that the report also reads.
