# Proposal

## Why

Issue #2395: every Ollama tier runs Ollama 0.34.4, which cannot run `embeddinggemma-2` on Linux. Ollama 0.40.0 added that model for Apple MLX only. Ollama 0.40.4 added multimodal embedding models through `llama-server`, the runner on Linux. An evaluation of `embeddinggemma-2` as the RAG embedding model needs a tier that can run it. The current release is 0.40.12.

`k8s/llm/profiles/ollama-profiles.yaml` pins `ollama/ollama:0.34.4` in 18 places: the `ollama` container and the `own-model-directory` init container of each of the nine tiers. No check stops a tier from running another release than the others, or a release below 0.40.4.

## What Changes

- Set the image of each `ollama` container and each `own-model-directory` init container in `k8s/llm/profiles/ollama-profiles.yaml` to `ollama/ollama:0.40.12`.
- Add the invariant test `test_every_ollama_tier_runs_one_release_that_serves_multimodal_embedding_models` to `tests/invariants/test_k8s_manifests.py`. It fails when two containers name different images, when the repository is not `ollama/ollama`, or when the tag is below 0.40.4.
- Update `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`: `applies_to` is `tool:ollama@0.40.*`, and the source of the keep-alive rule is the 0.40.12 scheduler, which has the same rule as 0.34.4.
- The change carries a spec delta, because a manifest is observable. It creates the capability `ollama-release-pin`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `ollama-release-pin`: every Ollama tier and its init container run one Ollama release, 0.40.4 or later.

### Modified Capabilities

None.

## Impact

- Manifest: `k8s/llm/profiles/ollama-profiles.yaml`. Argo CD applies it after the merge.
- Tests: `tests/invariants/test_k8s_manifests.py`.
- Knowledge base: `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`.
- Rollout: each tier is a DaemonSet with the default rolling update, and each tier runs on at most one node today. The old pod stops before the new pod starts, so each tier serves no request while its node pulls the image and the new pod starts. Argo CD applies all nine DaemonSets in one sync, so the tiers restart at about the same time. A loaded model loads again on its next request.
- Model store: 0.40.12 reads the existing `manifests` directory, and it writes the manifest of a model pulled later to the new directory `manifests-v2`. It does not copy or convert an existing model. A return to 0.34.4 keeps every model that exists today. 0.34.4 does not read `manifests-v2`, so a model pulled under 0.40.12 must be pulled again after such a return.

## Feasibility

Checked on 2026-10-28 against the release notes, the source at tag `v0.40.12`, and temporary pods of `ollama/ollama:0.40.12` on the cluster. The pods had the security context of the tiers (UID 10001, read-only root file system, all capabilities dropped). They mounted the node's model directory read-only and set `OLLAMA_NOPRUNE=1`, or kept models in an emptyDir only. They ran on the node with two Quadro P6000 cards (compute 6.1) and on the node with two Tesla PG500-216 cards (compute 7.0), the two oldest GPU families of the cluster.

- **GPU support.** `docs/gpu.mdx` at v0.40.12 supports compute 5.0 and later with driver 550 or later, and compute 5.0 to 6.2 with driver 570 or later. The 0.34.4 document has the same rules. The nodes run drivers 580 and 615. In both pods the `cuda_v13` libraries skipped the card, and the `cuda_v12` libraries found both cards (`inference compute ... library=CUDA compute=6.1` and `compute=7.0`).
- **Settings.** `envconfig/config.go` at v0.40.12 reads every variable that the tiers set: `OLLAMA_HOST`, `OLLAMA_MODELS`, `OLLAMA_CONTEXT_LENGTH`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_NUM_PARALLEL`, `OLLAMA_KV_CACHE_TYPE`, `OLLAMA_NO_CLOUD`, `OLLAMA_SCHED_SPREAD` and `OLLAMA_KEEP_ALIVE`. `api.DefaultOptions()` takes `OLLAMA_CONTEXT_LENGTH` before the default that depends on VRAM, as 0.34.4 does. `SetupLlamaServerCommandEnv` in `llm/llama_server.go` starts `llama-server` with the environment of Ollama, so `LLAMA_ARG_CACHE_RAM` still bounds the prompt cache of `ollama-64gib`.
- **Existing models.** 0.40.2 copied each model to a llama.cpp form on its first run. Pull request ollama/ollama#18908 (v0.40.3) disabled that copy, and `server/routes.go` at v0.40.12 still has it disabled. `/api/tags` of each pod listed the same models as the live 0.34.4 tier on its node (18 and 9). A chat model generated text on compute 6.1.
- **Embedding vectors.** With the `OLLAMA_KV_CACHE_TYPE` of the live tier (`q8_0`), `qwen3-embedding:0.6b` vectors from 0.40.12 had a cosine of 0.9995 to 0.9997 against the live 0.34.4 vectors for the same three texts, on both GPU families. The Qdrant collections stay valid. The probe of `/api/show` still gives `embedding_length` 1024.
- **embeddinggemma-2.** `embeddinggemma-2:270m` and `embeddinggemma-2:740m` (Q8_0) pulled and ran through the `llamacpp` runner on both GPU families: 768-dimension vectors, no NaN value, and a cosine of 0.9999 between GPU and CPU (`num_gpu: 0`). The text vectors of the two tags were the same.
- **Start-up writes.** At start, 0.40.12 prunes blobs that no manifest names, as 0.34.4 does, and it skips the prune when a manifest does not parse. It reads every existing manifest, so it prunes no blob of an existing model. It creates `manifests-v2` in the model directory, which is the writable host path of the tier.
- **Egress.** 0.40.12 adds a request for model recommendations to `ollama.com`. `refresh` in `server/model_recommendations.go` returns before the request when `OLLAMA_NO_CLOUD` is set, and every tier sets it.

## Existing Tool Considered

The upstream Ollama release and its official image cover the need. The change builds no code and deletes no internal code. The test checks only the pin.

Renovate's `kubernetes` manager matches the manifests under `k8s/` (#2323). It has opened no pull request for `ollama/ollama`, and this change does not depend on it.
