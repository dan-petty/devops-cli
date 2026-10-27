# Proposal

## Why

Issue #2027: The gateway routes all embedding requests to `ollama-48gib-fast`. The `ollama-64gib-standard` tier holds the embedding model and receives zero embedding traffic. The gateway configuration sets `routing_strategy: least-busy`. With sequential batches, every tier has zero requests in flight. The LiteLLM router breaks zero-in-flight ties with Python's `min()` function, which always selects the first deployment.

## What Changes

- `k8s/llm/gateway/config.yaml` configures a routing group for `qwen3-embedding:0.6b` with `routing_strategy: simple-shuffle`.
- The gateway keeps `least-busy` for generation models and shuffles embedding requests between the two order 1 tiers.
- The change modifies gateway routing behavior and manifests, so it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: ADDED requirement for the embedding group's routing strategy.

## Impact

- Manifests: `k8s/llm/gateway/config.yaml`.
- Documents: `k8s/README.md`.
- Tests: `tests/test_k8s_llm_gateway.py`.

## Feasibility

- The LiteLLM 1.103.0 source in the gateway pod shows how `least-busy` operates.
- `LeastBusyLoggingHandler` in `/app/.venv/lib/python3.13/site-packages/litellm/router_strategy/least_busy.py` runs `_least_busy`.
- The function returns `healthy_deployments[min(range(len(healthy_deployments)), key=lambda index: counts[index])]`.
- When in-flight counts are zero, Python's `min()` function returns the first index every time.
- In LiteLLM 1.103.0, `Router` supports `routing_groups` in `router_settings`.
- An isolated Python test in the pod confirmed that `routing_groups` with `simple-shuffle` distributes requests evenly over both order 1 deployments.
- The order filter runs before the routing strategy, so order 2 deployments receive traffic only when both order 1 deployments fail.

## Existing Tool Considered

LiteLLM 1.103.0 includes `routing_groups` and the `simple-shuffle` strategy. Nothing new is built. The change configures the existing `routing_groups` option in `k8s/llm/gateway/config.yaml`.
