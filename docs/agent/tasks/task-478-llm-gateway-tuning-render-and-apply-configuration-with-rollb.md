# Task 478: LLM Gateway Tuning Render and Apply Configuration With Rollback

**Issue**: [#478](https://github.com/dan-petty/devops-cli/issues/478)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `scope/k8s`
**Feasibility**: Verified against real system manifests: `k8s/llm/profiles/ollama-profiles.yaml` declares DaemonSet `OLLAMA_CONTEXT_LENGTH` values (48000 for 16gib, 128000 for 48gib, 160000 for 64gib), `k8s/llm/gateway/configmap.yaml` has mismatched `max_input_tokens: 96000` on 16gib-fast and superfluous `weight` fields under `least-busy` routing strategy.

---

## 1. Description & Objectives

The LLM gateway ConfigMap (`k8s/llm/gateway/configmap.yaml`) was previously maintained by hand: `max_input_tokens` values, per-tier Ollama entries, and routing weights were copied manually, and a test only verified they matched a hand-written copy in `k8s/gpu_matrix.py`. This was error-prone (`16gib-fast` declared 96000 against a 48000 context length) and the `weight` fields were meaningless because the router uses `routing_strategy: least-busy`, which LiteLLM ignores.

This deliverable adds `devops ai gateway render`, which parses Ollama profiles and services, derives each tier's `max_input_tokens` from `OLLAMA_CONTEXT_LENGTH`, eliminates all `weight` fields, shows a unified diff against `k8s/llm/gateway/configmap.yaml`, and writes the file with `--apply` without making any Kubernetes API calls. Rollback is handled via a revert PR.

#### Key Deliverables:
- [x] Command `devops ai gateway render` with `--apply` flag in `src/devops_cli/commands/ai_gateway.py`.
- [x] Pure parsing and rendering logic in `src/devops_cli/ai/gateway_render.py`:
  - `load_tier_context_lengths`: extracts `OLLAMA_CONTEXT_LENGTH` from DaemonSets in `k8s/llm/profiles/ollama-profiles.yaml`.
  - `load_service_context_lengths`: maps Service names in `k8s/llm/profiles/services.yaml` to their tier context length.
  - `render_gateway_config`: removes all `weight` fields, updates `max_input_tokens` to tier context length, preserves absence on `devops-background` and unwindowed deployments.
  - `diff_gateway_config`: computes unified diff against existing ConfigMap content.
- [x] Replaced `test_gateway_routing_entries_generation` in `tests/test_k8s_gpu_matrix.py` with `test_rendered_gateway_configmap_matches_ollama_profiles`, verifying ConfigMap entries, context lengths, and absence of weights.
- [x] Updated `k8s/llm/gateway/configmap.yaml` via `render --apply`:
  - `max_input_tokens` for `ollama-16gib-fast` corrected to 48000.
  - `max_input_tokens` for `ollama-64gib-standard` updated to 160000.
  - Removed all 15 `weight` fields.
- [x] Updated tests in `tests/test_k8s_llm_gateway.py` to reflect removal of `weight` fields and context length alignment.
- [x] Unit and integration tests for `devops ai gateway render` in `tests/test_ai_gateway_render.py`.
- [x] Changelog fragment `changelog.d/478.md`.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
