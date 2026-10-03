# Task: The Slow Tier Keeps Its Embedding Model and qwen3-coder Loaded and Leaves Every Interactive Pool (#1064)

**Issue**: [#1064](https://github.com/dan-petty/devops-cli/issues/1064)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
#1061 set `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` to `"1"` on every Ollama tier. The gateway still sent ollama-48gib-slow both embedding groups and five chat groups, so each chat request routed there evicted the embedding model and each embedding evicted the chat model:
- During a review pinned to `qwen3-coder:30b`, the tier loaded a runner 10 times in about four minutes, alternating bge-m3 and qwen3-coder, with one runner loaded after each load.
- 6 of 124 `/api/embed` requests waited 31 to 40 s, past the client's 30 s embedding read timeout. The first such failure turns RAG off for the rest of the run, and embeddings stopped while chat calls continued.

ollama-48gib-slow becomes the background tier, outside every interactive and review pool. It keeps two models loaded, its embedding model and `qwen3-coder:30b`, and the gateway sends it no other. This is the one exception to #1061's one-model rule; #1061's task file is unchanged.

## Key Changes
- **`k8s/llm/profiles/ollama-profiles.yaml`**: DaemonSet `ollama-48gib-slow` sets `OLLAMA_MAX_LOADED_MODELS: "2"` and adds `OLLAMA_KEEP_ALIVE: "-1"`, each with a one-line reason. `OLLAMA_NUM_PARALLEL` stays `"1"` on every tier. The header comment names the exception.
- **`k8s/llm/gateway/configmap.yaml`**:
  - The ollama-48gib-slow deployments of `devops-chat`, `devops-review`, `qwen3-coder:30b`, `gemma4:31b` and `qwen3.8:27b` are deleted. `qwen3-coder:30b` still copies `devops-review`'s qwen3-coder deployments exactly.
  - Both `embeddinggemma:300m` groups and the ollama-16gib-fast `bge-m3:latest` deployment are deleted. `bge-m3:latest` has one deployment, on ollama-48gib-slow, with `model_info.mode: embedding`.
  - `devops-background` is added: `ollama_chat/qwen3-coder:30b` on ollama-48gib-slow, with `timeout: 1100` and `num_retries: 0` in `litellm_params` and no `max_input_tokens` (see Trade-offs).
  - `router_settings.fallbacks` gains `devops-review: [devops-background]`, and no `devops-chat` rule. The pinned groups stay out of every fallback rule.
  - Comments explain the background tier's role, the timeout, the missing window, the fallback on gateway timeouts and the missing `devops-chat` rule. The `devops-review` comment names the interactive tiers instead of vLLM.
- **`src/devops_cli/k8s/gpu_matrix.py`**: `get_gateway_routing_entries` returns the new `model_list`, 19 entries.
- **Tests**:
  - `tests/test_k8s_llm_gateway.py`: `test_every_ollama_tier_keeps_one_model_and_serves_one_request` expects `"1"` for both settings on every tier except `OLLAMA_MAX_LOADED_MODELS: "2"` on ollama-48gib-slow, and reads `OLLAMA_KEEP_ALIVE` (`"-1"` there, unset elsewhere). `test_gateway_configmap_virtual_models` expects `devops-background`, the three fallback rules and no `embeddinggemma:300m`. `test_gateway_review_pool_spans_ollama_backends` and `test_gateway_routes_to_provider_vram_services` expect no slow-tier deployment in the review pool and one `bge-m3:latest` base.
  - New: `test_the_slow_tier_serves_embeddings_and_devops_background_alone` requires every non-embedding deployment on ollama-48gib-slow to belong to `devops-background`, and `devops-background` to have exactly that one deployment. `test_devops_background_frees_its_slot_before_the_review_client_gives_up` requires its timeout to be under `DEFAULT_REVIEW_TIMEOUT_SECONDS` and `num_retries` to be 0.
  - `test_a_review_model_has_a_group_of_its_review_deployments_alone` also requires that no group sets a top-level `model_info.max_input_tokens` on a pinned group's backend model, since LiteLLM would make it the pinned group's window.
  - `tests/test_k8s_gpu_matrix.py::test_gateway_routing_entries_generation` expects 19 entries equal to the ConfigMap.
- **`k8s/README.md`**: the gateway section describes `devops-review`'s interactive tiers, the `bge-m3:latest` embedding group and `devops-background`, with the environment-override recipe for `devops review path --watch` (its analysis, verification and compose tasks), `devops ai pipeline`, `devops ai agents` and `devops ai analyze`. The `ollama/<model>` bullet, a route the ConfigMap no longer has, is replaced, and the embedding example names `bge-m3:latest`.
- **`src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`**: the Kubernetes guidance shows the tier manifest's concurrency (one model loaded, one request at a time) and names the slow tier's exception, instead of recommending two slots. It no longer names a KV cache type, which differs by tier (`q4_0` on the 16 GiB tier, `q8_0` on the others).
- **`changelog.d/1064.md`**: the fix under `### Fixed`, the new group under `### Added`, the deleted groups under `### Removed`.

## Acceptance Criteria
- [x] ollama-48gib-slow sets `OLLAMA_MAX_LOADED_MODELS: "2"` and `OLLAMA_KEEP_ALIVE: "-1"` with one-line reasons; `OLLAMA_NUM_PARALLEL` is `"1"` on every tier; the header names the exception.
- [x] The gateway sends ollama-48gib-slow no interactive or review traffic, `bge-m3:latest` has one deployment there with `mode: embedding`, and nothing is left commented out.
- [x] `devops-background` is the only chat group with a slow-tier deployment, and `devops-review: [devops-background]` is the only new fallback rule.
- [x] `get_gateway_routing_entries` returns the 19 ConfigMap entries.
- [x] Each new or changed test failed on the previous manifests and passes now, except the pinned-group window clause, which passes on them too and fails when `devops-background` sets `model_info.max_input_tokens`. The tests read only the repository's files and call no gateway, Ollama or model.
- [x] `k8s/README.md` says what `devops-background` is for and how to use it, and names `bge-m3:latest` in its examples.
- [x] `uv run devops ci` passes.
- Pending a person: apply the profiles, then the ConfigMap, then restart the gateway, and note the time: `kubectl apply -k k8s/llm/profiles && kubectl apply -f k8s/llm/gateway/configmap.yaml && kubectl -n llm rollout restart deploy/llm-gateway`.
- Pending a person: during a `devops-background` job, `kubectl -n llm logs ds/ollama-48gib-slow --since=15m | grep -E 'fits alongside existing models|loaded runners count=|predicted to exceed available memory, evicting'` shows `fits alongside existing models` and `loaded runners count=2`, and no `predicted to exceed available memory, evicting`.
- Pending a person: `kubectl -n llm logs ds/ollama-48gib-slow --since=15m | grep -E 'POST +"/api/(chat|embed)'` shows `/api/embed`, plus `/api/chat` only while a `devops-background` job runs. No `/api/embed` takes over 30 s during a generation; if its p95 is over about 2 s, say so on #1064.

## Trade-offs
- Reviews lose the slow tier's share: weight 1 of 16 in `qwen3-coder:30b` and 1 of 22 in `devops-review`. Its review calls had a median of 37.2 s against 21 to 25 s on the other two tiers.
- Embeddings have no failover. LiteLLM v1.103.0 applies no per-deployment `timeout` or `num_retries` to `ollama/` embeddings, so a hung tier would not fail over within the client's 30 s. A restart of the slow tier's Ollama pod pauses RAG; once #1065 lands, a review carries on without it.
- With `OLLAMA_KEEP_ALIVE: "-1"`, a third model on the slow tier evicts one of the two. The embedding-model switch (#481) runs `ollama stop` on the old model first. A request that sends its own `keep_alive`, such as `devops ai prewarm`, overrides the tier's for that model.
- `devops-background` sets no `max_input_tokens`. LiteLLM v1.103.0 writes a deployment's top-level `model_info` into the cost-map entry that every deployment of the same backend model reads (`Router._register_deployment_in_model_cost`). A Router built offline from this ConfigMap with a 128,000-token window on `devops-background` gave that window to the six other `ollama_chat/qwen3-coder:30b` deployments (`devops-coder`, `devops-reasoning`, two in `devops-review`, two in `qwen3-coder:30b`); at 140,000 tokens `devops-review` kept only `gpt-oss:20b` on ollama-16gib-fast, and `qwen3-coder:30b` and `devops-coder` raised `ContextWindowExceededError`. Without it, none of them has a window, as before. The group has one deployment and no context-window fallback, so the tier's `OLLAMA_CONTEXT_LENGTH` of 128000 is its limit, and the gateway does not refuse a longer prompt first.
- `devops-review: [devops-background]` also fires on gateway timeouts. The router's timeout (1,500 s) outlasts the review client's (1,200 s), so when a `devops-review` call still fails by timeout after the router's retries, the client has already given up, and the background tier spends up to 1,100 s of its one slot on a reply nobody reads. LiteLLM's proxy does not cancel a non-streaming call when its client disconnects. Lowering the `devops-review` deployments' timeout under the client's is not part of this item.
- The gateway health-check routing item owns liveness. It should not probe `devops-background`, whose one deployment would queue a probe behind real work at one request at a time.
