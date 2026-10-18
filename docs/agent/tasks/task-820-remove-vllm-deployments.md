# Task: Remove the Code, Config and Policies Left Over from the Removed vLLM Deployments (#820)

**Issue**: [#820](https://github.com/dan-petty/devops-cli/issues/820)
**Scope**: scope/ai, scope/k8s
**Feasibility**: Feasible - Confirmed through code and manifest search that vLLM deployments and profiles were removed in #734, leaving dead settings, routes, scale commands, and network policies.

## Description
fdd4d0f (#734) deleted the vLLM profiles (`k8s/llm/profiles/vllm-profiles.yaml`). However, numerous references across `src/`, `k8s/`, `tests/`, and `.devcontainer/` still addressed the removed vLLM Services or described the stack as running vLLM. In accordance with zero-legacy-remnant invariants and pre-1.0 alpha cleanliness, this task comprehensively purged all dead vLLM code, defaults, CLI commands, FastMCP tools, Kubernetes manifests, and network policies without introducing compatibility shims.

- **Defaults, routes, and settings**:
  - Removed `DEFAULT_VLLM_16GIB_CLUSTER_URL` and `DEFAULT_VLLM_48GIB_CLUSTER_URL` from `src/devops_cli/config/defaults.py`.
  - Removed `vllm_url` field from `AIConfig` in `src/devops_cli/config/settings.py`.
  - Updated `CONST_AI_BACKENDS` in `src/devops_cli/config/constants.py` to `("ollama",)`.
  - Updated `DEFAULT_GATEWAY_ROUTES` in `src/devops_cli/ai/gateway.py` so that `devops-coder` routes to `qwen2.5-coder:14b` and `devops-reasoning` routes to `qwen3-coder:30b`, both on `DEFAULT_OLLAMA_CLUSTER_URL`.
  - Removed `scale_vllm` and `_execute_kubectl_scale` from `src/devops_cli/ai/gateway.py`.
  - Cleaned `probe_backend` and `_resolve_backend_url` in `src/devops_cli/ai/gateway.py`.
  - Removed `vllm_url` fallback logic from `src/devops_cli/ai/spend/pricing.py`.
- **Commands and MCP tools**:
  - Removed `devops ai gateway scale` CLI command (`scale_cmd`) and `_render_scale_table` from `src/devops_cli/commands/ai_gateway.py`.
  - Removed `ai_vllm_scale` FastMCP tool from `src/devops_cli/ai/mcp/server.py`.
  - Updated `devops ai gateway load` and `src/devops_cli/ai/pool_load.py` to remove vLLM server busy-share and waiting queue queries (`busy_share`, `mean_waiting`, `max_waiting`), reporting gateway call-seconds and GPU utilization cleanly.
  - Cleaned docstrings in `src/devops_cli/telemetry/instruments.py` and `src/devops_cli/ai/gateway_tune.py`.
- **Kubernetes manifests and policies**:
  - Deleted `k8s/llm/profiles/networkpolicy.yaml` (`vllm-profiles-perimeter`) and removed its entry from `k8s/llm/profiles/kustomization.yaml`.
  - Removed `vllm` and `vllm-single` from perimeter exclusions in `k8s/llm/networkpolicy.yaml`.
  - Removed port 8000 egress rules from `k8s/llm/gateway/networkpolicy.yaml`, `k8s/llm/portkey/networkpolicy.yaml`, and `k8s/monitoring/networkpolicy.yaml`.
  - Removed `vllm-backend` virtual key and upstream target from `k8s/llm/portkey/configmap.yaml`.
  - Cleaned comments and table references in `k8s/llm/values-open-webui.yaml`, `k8s/llm/profiles/README.md`, and `k8s/llm/gateway/configmap.yaml`.
- **Devcontainer**:
  - Updated `.devcontainer/devcontainer.json` `ollama.endpoint` from `http://vllm-16gib.llm.svc.cluster.local:8000` to `http://ollama-16gib.llm.svc.cluster.local:11434`.
  - Added a file-only regression test in `tests/test_devcontainer.py` asserting that `ollama.endpoint` matches an active Service and port in `k8s/llm/profiles/services.yaml`.
- **Generic engine support preservation**:
  - Maintained generic continuous batching support in `CONST_CONTINUOUS_BATCHING_ENGINES` (`vllm`, `sglang`, `tgi`), KV-cache inspection in `src/devops_cli/ai/gateway_bench.py`, OpenAI provider compatibility docstring in `src/devops_cli/ai/providers/openai.py:20`, and sample data in `src/devops_cli/ai/review/samples.json`.

## Acceptance Criteria
- [x] Each item in Scope & Deliverables completed cleanly with zero legacy shims.
- [x] `grep -rn -i "vllm" src k8s tests .devcontainer` reports only authorized generic continuous batching engine support, review sample data, and regression tests.
- [x] `devops ai gateway load` reports gateway and GPU figures with zero vLLM columns.
- [x] `ollama.endpoint` in `.devcontainer/devcontainer.json` points to `http://ollama-16gib.llm.svc.cluster.local:11434`.
- [x] Added regression test `test_vllm_dead_settings_commands_and_mcp_tools_are_removed` in `tests/test_codebase_hygiene_and_shims.py`.
- [x] Added file-only test `test_devcontainer_ollama_endpoint_matches_gateway_service_and_port` in `tests/test_devcontainer.py`.
- [x] Documentation regenerated and verified clean via `uv run devops docs check`.
- Pending a person: `uv run devops ci` on this branch; it is this PR's own check, which readiness reads.
- Pending a person: after deploying with `devops k8s deploy-stack --stack all`, verify that all cluster workloads remain healthy with updated network policies.

## Measurements
The regression test suites, run offline with `uv run pytest`:

| Test Suite | Call Duration | Tests Passed |
| :--- | ---: | ---: |
| `tests/test_codebase_hygiene_and_shims.py` | 13.68 s | 18 |
| `tests/test_ai_gateway.py` | 3.82 s | 23 |
| `tests/test_k8s_llm_gateway.py` | 3.12 s | 33 |
| `tests/test_k8s_network_policies.py` | 2.95 s | 26 |
| `tests/test_ai_gateway_tune.py` | 2.68 s | 38 |
| `tests/test_llm_pool_metrics.py` | 2.10 s | 18 |
| `tests/test_ai_gateway_portkey.py` | 1.85 s | 11 |
| `tests/test_devcontainer.py` | 0.52 s | 10 |
