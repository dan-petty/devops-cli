# Task: Refactor GPU Matrix, Eliminate vLLM References and Extract Static JSON Asset (#1223)

**Issue**: [#1223](https://github.com/dan-petty/devops-cli/issues/1223)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Refactor the Kubernetes GPU configuration matrix and service alias system (`src/devops_cli/k8s/gpu_matrix.py`). The previous implementation spanned 845 lines of code primarily composed of sprawling hardcoded Python dictionary literals (`_MATRIX_ENTRIES`, `PROVIDER_SERVICE_ALIASES`, `SPEED_TIER_SERVICE_ALIASES`, and `get_gateway_routing_entries()`), relied on iterative loop attributes (`total_vram_gib`) computed dynamically, and retained 12 unused `vllm` hardware profiles and 8 unused `vllm-*` service aliases despite the cluster containing zero vLLM manifests.

This deliverable extracts all static matrix data into a structured JSON asset (`src/devops_cli/k8s/gpu_matrix.json`) containing:
1. **Profiles**: Exactly 12 Ollama hardware profiles spanning 1–4 GPUs and 16, 24, and 32 GiB per GPU, with precomputed `total_vram_gib` and optimized model mappings.
2. **Provider Service Aliases**: Standardized Ollama service aliases (`ollama-16gib` through `ollama-128gib`) on port 11434.
3. **Speed Tier Service Aliases**: Fast, standard, and slow tier aliases matching cluster manifests (`k8s/llm/profiles/services.yaml`).
4. **Gateway Routes**: Canonical 19 model routing rules matching `k8s/llm/gateway/configmap.yaml`.

The Python module `src/devops_cli/k8s/gpu_matrix.py` is reduced by over 700 lines to a concise (~125 lines) typed interface that parses the JSON asset once via `@functools.cache`. Obsolete `vllm` backends and CLI options are purged, aligning the matrix with the homelab Ollama-only architecture.

## Acceptance Criteria
- [x] Extract `profiles`, `provider_service_aliases`, `speed_tier_service_aliases`, and `gateway_routes` into `src/devops_cli/k8s/gpu_matrix.json`.
- [x] Eliminate all vestigial `vllm` profiles, service aliases, and backend literals from `src/devops_cli/k8s/gpu_matrix.py` and `src/devops_cli/commands/k8s/gpu_matrix.py`.
- [x] Replace iterative attribute population in loops with validated schema models (`GpuProfile`).
- [x] Ensure `get_gateway_routing_entries()` returns the 19 LiteLLM routes matching `k8s/llm/gateway/configmap.yaml`.
- [x] Update test suite in `tests/test_k8s_gpu_matrix.py` covering all 12 profiles, service aliases, filtering, CLI table/json formatting, and gateway consistency.
- [x] Pre-push Gated CI validation suite passes with 100% green status.
- Pending a person: review and merge PR on GitHub.

## Measurements
Regression and unit tests executed via `uv run pytest tests/test_k8s_gpu_matrix.py`:
- 12 passed in ~16.7s.
- Full Kubernetes test suite (`tests/test_k8s*`): 654 passed in ~35.8s.
