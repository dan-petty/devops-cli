# Proposal

## Why

Issue #2825: the gateway enforces no context window on any deployment. A long prompt can reach a small tier, and Ollama then cuts the prompt without an error.

Three facts cause this:

- `devops-review` has three deployments with three windows: 262144 on `ollama-48gib-fast`, 160000 on `ollama-64gib-standard` and 131072 on `ollama-16gib-fast`. The router picks the deployment with the fewest requests in flight, so a prompt of 140000 tokens can reach the smallest one.
- The config writes `model_info` inside `litellm_params` for `devops-chat`, `gemma4:31b`, `qwen3.8:27b` and `deepseek-r1:70b`. LiteLLM reads the window only from the top-level `model_info` of a deployment, so those four windows have never had an effect.
- Two `context_window_fallbacks` rules point from `devops-chat` to `devops-coder` and `devops-reasoning`, and from `devops-coder` to `devops-reasoning`. No target has a larger window than its source, so the rules cannot help.

## What Changes

- Every `ollama_chat` deployment of `k8s/llm/gateway/config.yaml` gets `max_input_tokens` in its top-level `model_info`, equal to the context length of its tier. The four misplaced blocks move to the top level.
- The `context_window_fallbacks` rules go. The key goes with them.
- The comments of the config and the gateway sections of `k8s/README.md` and `k8s/llm/profiles/README.md` say what the router does now.
- A test holds the shape: a window on each deployment, equal to its tier, and no `model_info` inside `litellm_params`.
- This change fits in one pull request.
- This change adds two requirements to `ai-gateway-routing`. The gateway config is a manifest, so its behavior is observable.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: adds the window of each chat deployment and the end of the useless window fallbacks.

## Impact

- Cluster: the gateway Deployment rolls when Argo CD syncs the new ConfigMap. No Ollama tier changes.
- A prompt longer than the window of a deployment no longer reaches it. A prompt longer than every window of a group ends with a `ContextWindowExceededError` from the gateway, after its plain fallbacks.
- `devops ai gateway tune` reads `model_info.max_input_tokens` from `/model/info`. It now sees the window of each deployment and keeps its probe prompt within 90% of it.
- `devops-review` falls back to `devops-background` (128000). A prompt longer than that window now fails there with an error. Before, Ollama cut it without an error.

## Feasibility

Measured on 2026-10-31 against the gateway image `ghcr.io/berriai/litellm:v1.103.0`, read-only.

- Source: `router.py` of the image has the same SHA-256 as `router.py` of `pip install litellm==1.103.0` in a scratch directory. `_pre_call_checks` reads `max_input_tokens` from `get_router_model_info`. That call merges the cost-map entry of the backend model with the top-level `model_info` of the deployment. It never reads `litellm_params.model_info`.
- Live gateway: `GET /model/info` from inside the gateway pod, with the key read from the pod environment and not printed. `max_input_tokens` is `None` for all ten deployments of `devops-chat`, `devops-coder`, `devops-reasoning`, `devops-review`, `qwen3-coder:30b` and `gpt-oss:20b`. The two `devops-chat` deployments show their 262144 and 160000 only as `litellm_params.model_info`.
- Router of the same version built in process from the unchanged config. A prompt of 100000, 140000 and 200000 tokens leaves every deployment of `devops-chat` and of `devops-review` in the list. The router applies no window.
- Router with the windows moved to the top level. Each deployment returns its own window, also where two deployments share one backend model (`qwen3-coder:30b` 262144 and 160000, `qwen3.8:27b` 262144 and 160000). Then `devops-review` keeps all three deployments at 100000 tokens, keeps `ollama-48gib-fast` and `ollama-64gib-standard` at 140000, and keeps `ollama-48gib-fast` alone at 200000. `devops-chat` keeps `ollama-48gib-fast` alone at 200000.
- Shared cost-map entry. A deployment that sets no window of its own reads the entry that the last registered deployment wrote. With only `devops-chat` fixed, `qwen3.8:27b` on `ollama-48gib-fast` reads 160000 and `devops-background` (tier 128000) reads 160000. Thus every `ollama_chat` deployment must set its own window.
- Live truncation, from inside the gateway pod, on the group `gpt-oss:20b` (one deployment, tier window 131072, `ollama ps` shows context 131072). A prompt of 100000 words returned HTTP 200 with `prompt_tokens` 100075. A prompt of 140000 words returned HTTP 200 with `prompt_tokens` 65538. Ollama cut the prompt without an error, to a little more than half of the window, not to the window.
- Two probes ran. The prompt stayed at or under 150000 tokens. The probes reached the gateway from inside the cluster, so the tunnel was not involved.
- The refine proposal on the issue suggested to drop `gpt-oss:20b` from `devops-review` and to set 160000 on the group. The evidence rejects it: a window on the top-level `model_info` of each deployment is enough, and `gpt-oss:20b` stays in the pool for the prompts that fit it.

## Existing Tool Considered

LiteLLM `enable_pre_call_checks` with a per-deployment `model_info.max_input_tokens`, which the config already turns on. Nothing is built. The change moves the existing keys to the place that LiteLLM reads, and removes the rules that cannot help.
