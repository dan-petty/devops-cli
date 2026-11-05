# Proposal

## Why

Issue #3567: the owner asks that the 48 GiB and 64 GiB Ollama tiers use `qwen3.8:27b` with its maximum context, keep it loaded, and run no other model until the configuration changes. The owner also asks that `qwen3.8:27b` replace `qwen3-coder:30b` in tasks and configs.

Today both tiers load up to two models (`OLLAMA_MAX_LOADED_MODELS` is 2, no keep-alive). The gateway sends them `qwen3-coder:30b`, `gemma4:31b`, `qwen3.8:27b`, `deepseek-r1:70b` on the 64 GiB tier, and an embedding model. A switch between models drops the KV cache and loads weights again. Issue #3485 records slow `devops-coder` replies on `ollama-48gib-fast` while a second chat model shares the tier.

## What Changes

- `ollama-48gib` and `ollama-64gib` set `OLLAMA_CONTEXT_LENGTH` 262144 (the 64 GiB tier had 160000, the 48 GiB tier had it already), `OLLAMA_NUM_PARALLEL` 1, `OLLAMA_MAX_LOADED_MODELS` 1 and `OLLAMA_KEEP_ALIVE` `-1`.
- The tier template of the 48 GiB tier loads one model. The render writes no embedding deployment for a chat tier.
- The gateway config sends `qwen3.8:27b` alone to `ollama-48gib-fast` and `ollama-64gib-standard`:
  - `devops-coder`, `devops-reasoning` and `devops-review` name `qwen3.8:27b`. `devops-coder` and `devops-reasoning` fall back to `devops-chat`, since they now name the model of `ollama-48gib-fast`.
  - The groups `qwen3-coder:30b`, `gemma4:31b` and `deepseek-r1:70b` are deleted. Nothing in the repository calls them.
  - The two embedding deployments on these tiers are deleted. `ollama-16gib-fast` is the second order of the embedding group.
  - The windows of the 64 GiB deployments follow the tier: 262144.
- `DEFAULT_GATEWAY_ROUTES` names `qwen3.8:27b` for `devops-coder` and `devops-reasoning`. Its `devops-embedding` route calls an embedding Service (`DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL`), since the default Ollama Service no longer serves an embedding model.
- `qwen3-coder:30b` is replaced by `qwen3.8:27b` in the defaults, the GPU matrix, the documents and the tests. The old name stays only in history (archived changes, `CHANGELOG.md`, measured numbers).
- A test fails if a second model, or an embedding model, returns to the two tiers.
- This change alters manifests and the gateway routes, so it carries a spec delta.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: the two large tiers load one model; embeddings and defaults follow.

## Impact

- Cluster: Argo CD restarts the pods `ollama-48gib` and `ollama-64gib` and the gateway when it syncs the merge. Clients see these changes:
  - `devops-coder` and `devops-reasoning` answer with `qwen3.8:27b`, not `qwen3-coder:30b`. The new model is dense and 27B, with thinking on by default.
  - `qwen3-coder:30b`, `gemma4:31b` and `deepseek-r1:70b` are no longer gateway models. `qwen3-embedding:0.6b` is no longer served on the two tiers.
  - The model stays loaded. A switch of model, and its reload, cannot happen on these tiers through the gateway.
  - The first request after a pod starts loads the model from the node model directory. `qwen3.8:27b` is in the model directory of both nodes (see Feasibility).
- Gateway: `k8s/llm/gateway/config.yaml`.
- Code: `src/devops_cli/k8s/gpu_thresholds.py`, `src/devops_cli/ai/gateway.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/k8s/gpu_matrix.json`.
- Documents: `k8s/README.md`, `k8s/llm/profiles/README.md`, the Ollama and pydantic-ai knowledge base, generated command documents.

## Feasibility

Checked on 2026-11-05, read-only:

- `ollama show qwen3.8:27b` on the pod of `ollama-48gib`: architecture `qwen35`, 27.3B parameters, context length 262144, capabilities completion, vision, tools, thinking.
- `ollama ps` on that pod: the model, loaded with 262144 context, takes 27 GB, 100% on the GPUs.
- `ollama list` on the pods of `ollama-48gib` (node with 2x RTX 3090) and `ollama-64gib` (node with 2x Tesla V100): both hold `qwen3.8:27b` (17 GB), pulled 36 hours before. These are the only two nodes that run the tiers (`kubectl -n llm get ds`: one pod each). The first load after a restart therefore reads the local file; no pull happens. Both directories still hold other models.
- VRAM of the 64 GiB tier: 2 x 32 GiB. The 27 GB figure leaves more than half free. The KV cache grows 3.3 GiB from 160000 to 262144 tokens (34 KiB a token with q8_0, from the measurement of #2822). Nobody loaded 262144 on this tier, and the test must not load a live tier, so this is an inference from the 48 GiB measurement, not a measurement.
- RAM of the 64 GiB tier: the proposal of #2382 recorded 15.3 GiB of RAM on node `gemini`. The node now reports 62.5 GiB (`kubectl describe node`, `node_memory_MemTotal_bytes`), and its peak use in 14 days was 13.4 GiB (Prometheus). The container limit of 12Gi and `LLAMA_ARG_CACHE_RAM` 4096 stay: one `llama-server` takes about 4 GiB, and the cache adds at most 4 GiB. A prompt cache entry above about 120000 tokens exceeds the 4096 MiB bound.
- The restarts of the 64 GiB pod seen on 2026-11-04 had exit code 255 at the time of a node restart, not an out-of-memory kill.
- The model has 27B parameters. `CONST_MIN_REASONING_MODEL_TIER_B` is 30, so a failover of `devops-reasoning` to a model that the gateway serves needs `--force`: no served model has 30B parameters. This change does not lower that threshold.
- `devops-embedding` in `DEFAULT_GATEWAY_ROUTES` is not a LiteLLM group; the gateway config has no such group. Only the route registry names it.
- A direct caller can still reach the tier: the NetworkPolicy `llm-default-perimeter` admits every pod of the `llm` namespace, the `monitoring` namespace and Traefik. `devops k8s configure-urls` points `ai.ollama_urls` at the default Ollama Service. A client that uses the `ollama` provider for embeddings through that URL would send `qwen3-embedding:0.6b` to the 48 GiB tier, and Ollama would unload `qwen3.8:27b`. This change does not add compensating code; it is reported as a follow-up.

## Existing Tool Considered

Ollama's own settings `OLLAMA_KEEP_ALIVE`, `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_CONTEXT_LENGTH`, the LiteLLM model list, and the existing `devops ai gateway render`. Nothing is built. The change deletes the embedding fallback of the render for a chat tier, the groups of the three other models, and the old model name.
