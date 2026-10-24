# Proposal

## Why

Issue #1969: the default routes of `devops ai gateway` named models that their tier does not hold, so a failover to them failed. `DEFAULT_GATEWAY_ROUTES` sent `devops-chat` to `qwen2.5-coder:7b` and `devops-coder` to `qwen2.5-coder:14b`, both on the Service `ollama-fast`, which selects the tier ollama-48gib. On 2026-10-24 no tier held `qwen2.5-coder:14b`, and ollama-48gib held neither model. A failover to `direct-ollama` also named `qwen2.5-coder:7b` on that tier.

## What Changes

- `devops-chat` names `qwen3.8:27b`, `devops-coder` and `devops-reasoning` name `qwen3-coder:30b`, and `devops-embedding` names `qwen3-embedding:0.6b`. The gateway config sends each of these models to the Service `ollama-48gib-fast`, and the tier ollama-48gib holds each of them.
- A failover to `direct-ollama` keeps the target model of the virtual model's default route, which calls the default Ollama tier without the gateway. The `qwen2.5-coder:7b` literal of that failover is gone. Before, an embedding failover went to a chat model.
- The Portkey `ollama-coder` target in `k8s/llm/portkey/configmap.yaml` names `qwen3-coder:30b`, because `tests/test_ai_gateway_portkey.py` binds it to the `devops-coder` route. That test now compares the two values and holds no model name of its own.
- A test fails when a route, or the route that a failover records, names a model that the gateway config does not send to the tier of the route's Service.
- The routes are what `devops ai gateway status`, `routes` and `failover` (and the MCP tools `ai_gateway_status`, `ai_gateway_routes` and `ai_gateway_failover`) show and gate, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ai-gateway-routing`: the route that `devops ai gateway` keeps for each virtual model, and the route that a failover records.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/gateway.py` (`DEFAULT_GATEWAY_ROUTES` and `_resolve_fallback_physical_route`).
- Manifest: `k8s/llm/portkey/configmap.yaml`.
- Tests: `tests/test_k8s_llm_gateway.py`, `tests/test_ai_gateway.py` and `tests/test_ai_gateway_portkey.py`. The capability gate tests write a route table whose `devops-coder` route is below the 30B floor of `devops-reasoning`, because no default route is below the floor of a virtual model that fails over to it. `test_default_routes_target_profiles` is removed: it repeated two route targets, and the new check binds every target to the gateway config.

## Feasibility

- On 2026-10-24, `kubectl -n llm get pods -l llm.devops.io/backend=ollama` showed pods for the tiers ollama-16gib, ollama-48gib, ollama-48gib-slow and ollama-64gib.
- `ollama list` in each pod showed `qwen2.5-coder:14b` on no tier, and `qwen2.5-coder:7b` on ollama-16gib and ollama-48gib-slow only.
- LiteLLM's `router_settings.fallbacks` in `k8s/llm/gateway/config.yaml` move the live traffic. The routes in the CLI are the record that the `devops ai gateway` commands show and gate.
- The routes cannot come from the gateway config at run time. The wheel and the service image hold only `src/devops_cli` (`[tool.hatch.build.targets.wheel]`, `COPY src/` in the `Dockerfile`), and the `configMapGenerator` of `k8s/llm/gateway/kustomization.yaml` reads `config.yaml` from its own directory. So the routes stay in the CLI, and a test binds them to the config.
- On the base commit, `test_every_gateway_route_and_failover_route_names_a_model_that_its_tier_serves` failed and named the five routes to `qwen2.5-coder:7b` and `qwen2.5-coder:14b`.

## Existing Tool Considered

LiteLLM's router is the tool that moves the live traffic, through `router_settings.fallbacks`. Nothing is built. The change edits the route table that the CLI already keeps and adds one test that reads the committed gateway config and manifests. It deletes the `qwen2.5-coder:7b` fallback literal in `_resolve_fallback_physical_route` and the test `test_default_routes_target_profiles`.
