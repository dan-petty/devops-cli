# Design

## Context

The LiteLLM AI Gateway routes inference and embedding requests to Ollama tiers. The gateway configuration sets `routing_strategy: least-busy` for all models. The `qwen3-embedding:0.6b` model group has two order 1 deployments: `ollama-48gib-fast` and `ollama-64gib-standard`.

Under `least-busy` routing, the gateway routes each request to the deployment with the fewest in-flight requests. Sequential embedding batches arrive when in-flight request counts are zero. The router picks the first deployment for every sequential request. Parallel batches wait in the single slot of that tier while the second tier idles.

## Decisions

- **Add a routing group for embeddings.** Configure `routing_groups` in `router_settings` in `k8s/llm/gateway/config.yaml`. Assign `group_name: embedding`, `models: [qwen3-embedding:0.6b]`, and `routing_strategy: simple-shuffle`.
- **Preserve global least-busy routing.** Generation requests keep `least-busy` routing to avoid queue accumulation behind long completions.
- **Rely on order-based fallback.** The router applies deployment order filtering before strategy selection. The gateway tries order 1 deployments first and falls back to order 2 tiers only when all order 1 tiers fail.

## Rejected Alternatives

- **Set weights or RPM under least-busy.** Rejected: `LeastBusyLoggingHandler` in LiteLLM 1.103.0 evaluates only request counts. The implementation ignores `weight` and `rpm` fields.
- **Change the global strategy to simple-shuffle.** Rejected: Generation models such as `devops-review` need `least-busy` to balance long running tasks across tiers.
- **Build an in-tree routing proxy.** Rejected: LiteLLM 1.103.0 already supports `routing_groups` natively without additional code or dependencies.
