# Design

## Decisions

- Add `checked: bool = True` to `GatewayRoute` (`src/devops_cli/ai/gateway.py`) so live `/model/info` deployments render health (`"✓ healthy"` / `"✗ degraded"`) while static fallback rows during unreachable or `/model/info`-unavailable probes preserve `self._active_routes` failover state, return `checked=False`, and display `"not checked"` in `_render_routes_table`.
- Reuse `_fetch_remote_routes` and `get_ai_api_key(settings)` inside `status_cmd` and `GatewayRouter.probe_gateway`, catching `AICredentialsError` cleanly in `status_cmd` while leaving `tier_health`'s `DevOpsCLIError` handling intact.
- Replace `devops-embedding` with `qwen3-embedding:0.6b` everywhere in `src/` and `tests/`, and accept an optional `provider` parameter in `plan_ai_benchmark` so `gateway` embedding benchmarks plan `/v1/embeddings` while `ollama` benchmarks keep `/api/embeddings`.
- Extend existing `test_every_gateway_route_and_failover_route_names_a_model_that_its_tier_serves` and `test_the_route_check_names_each_route_whose_tier_the_gateway_sends_no_such_model` in `tests/ai/benchmark/test_k8s_llm_gateway.py` to check `CONST_AI_GATEWAY_VIRTUAL_MODELS` and route `virtual_model` names against `k8s/llm/gateway/config.yaml` without exceeding `config_reads.toml` (`29`).

## Rejected alternatives

- Showing only live `/model/info` rows in `status`: rejected because it removes all fallback visibility when the gateway is down.
- Generating `CONST_AI_GATEWAY_VIRTUAL_MODELS` directly from Kubernetes YAML: rejected because wheels and service images package `src/devops_cli` without `k8s/`.
- Planning `/v1/embeddings` unconditionally: rejected because direct Ollama embedding benchmarks use `/api/embeddings`.
