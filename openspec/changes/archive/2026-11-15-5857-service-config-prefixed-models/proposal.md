# Proposal: #5857

## Why
With PR #5854, the in-cluster LLM gateway now supports prefixed model aliases: local models under `local/` and hosted provider models under provider namespaces like `openrouter/`. To ensure that telemetry, spend accounting, and cluster service calls use the standard prefixed conventions consistently, the cluster service configuration template (`k8s/devops/configmap.example.yaml`) and in-cluster consumer manifests (`k8s/llm/values-open-webui.yaml`, `k8s/monitoring/grafana-values.yaml`) must be updated to use these prefixed names. Closes #5857.

## What Changes
- Update `k8s/devops/configmap.example.yaml` to specify `openrouter/deepseek/deepseek-v4.1-flash-1017` for all chat and implement slots and `local/qwen3-embedding:0.6b` for the embedding slot.
- Update `k8s/llm/values-open-webui.yaml` to use `local/devops-chat` for `DEFAULT_MODELS` and `local/qwen3-embedding:0.6b` for `RAG_EMBEDDING_MODEL`.
- Update `k8s/monitoring/grafana-values.yaml` to use `local/qwen3.8:27b` for base and large model mappings.
- Update validation and test assertions in `tests/config/test_k8s_devops_runtime.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`, and `tests/ai/spend/test_hosted_group_prices.py`.
- Update documentation references in `docs/CLUSTER.md`, `docs/roadmap/implement.md`, and `docs/roadmap/stage.md`.

## Capabilities
- `roadmap-service-deployment`: Deploy and configure the roadmap service and in-cluster jobs.

## Impact
- Cluster Jobs and Roadmap Service use explicit provider and local prefixes when calling the gateway.
- Open WebUI and Grafana LLM plugin connect to local gateway models via explicit `local/` prefixes.
- Spend tracking attributes all requests cleanly according to route and prefix.

## Feasibility
- Verified against the live LLM Gateway routing and alias configurations deployed in PR #5854.
- All aliases are registered in the gateway's `model_group_alias` map.

## Existing Tool Considered
ConfigMap templates and Helm value files provide declarative, revision-tracked configuration without extra tooling.
