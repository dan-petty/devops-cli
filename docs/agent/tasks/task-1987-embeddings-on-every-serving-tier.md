# Task: The Gateway Sends Embeddings to Every Serving Ollama Tier, Fastest First (#1987)

**Issue**: [#1987](https://github.com/dan-petty/devops-cli/issues/1987)
**Scope**: scope/k8s
**Feasibility**: Measured on the cluster with one RAG-sized `/api/embed` batch (32 chunks of 2,400 characters). Warm, `ollama-16gib` took 0.95 s, `ollama-64gib` took 4.4 s, and `ollama-48gib-slow` took 12 to 30 s. At an 8,192-token context, the embedder used 2.2 GB on `ollama-16gib` and 2.9 GB on `ollama-64gib`. At its 32,768-token default it used 3.1 GB and 5.2 GB. `litellm.embedding(..., num_ctx=2048)` in the gateway's own LiteLLM 1.103.0 loaded the model with a 2,048-token context, so the gateway forwards `num_ctx` to Ollama. The router of that version reads `order` for order-based fallback (`litellm/router.py` calls `litellm.utils._get_deployment_order`).

## Description
The gateway sent every `qwen3-embedding:0.6b` request to `ollama-48gib-slow`, the background tier. There, one batch took longer than the RAG client's 15 s timeout. So `devops ai rag index` stopped after 128 of 16,417 chunks, and the duplicate check of `devops roadmap intake` failed.

The model is now on every serving tier, and the gateway's group has one deployment per tier. LiteLLM's `order` puts `ollama-48gib-fast` and `ollama-64gib-standard` first. `ollama-16gib-fast` and `ollama-48gib-slow` are fallbacks: the chat model of the first leaves no VRAM for the embedder, and the second is slow. Each deployment sends `num_ctx: 8192`, which is `CONST_RAG_MAX_CHUNK_TOKENS`, so the largest RAG chunk fits and the embedder needs less VRAM.

A tier that the gateway sends embeddings to keeps two models loaded (`OLLAMA_MAX_LOADED_MODELS: "2"`). Ollama loads the second model only when both fit in VRAM, and otherwise unloads the idle one. `OLLAMA_NUM_PARALLEL` stays `"1"` on every tier, so each KV cache holds one context (#1061).

## Key Changes
- **`k8s/llm/gateway/configmap.yaml`**: four `qwen3-embedding:0.6b` deployments, each with `order` and `num_ctx: 8192`.
- **`k8s/llm/profiles/ollama-profiles.yaml`**: `ollama-16gib`, `ollama-48gib` and `ollama-64gib` keep two models loaded. The header gives the rule.
- **`tests/test_k8s_llm_gateway.py`**: the route test pins each embedding deployment with its order. `test_every_embedding_deployment_holds_the_largest_rag_chunk` requires `num_ctx` equal to `CONST_RAG_MAX_CHUNK_TOKENS`. The tier test derives the tiers that keep two models from the Services of the embedding deployments.
- **`tests/test_k8s_gpu_matrix.py`**: the rendered model list has 22 entries.
- **`k8s/README.md`**, **`k8s/llm/profiles/README.md`** and the Ollama knowledge base page describe the placement and the pull command.

## Acceptance Criteria
- [x] An offline test requires one embedding deployment per serving tier with the order above, and `num_ctx` equal to `CONST_RAG_MAX_CHUNK_TOKENS`.
- [x] An offline test requires two loaded models on every tier that the gateway sends embeddings to, one on every other tier, and `OLLAMA_NUM_PARALLEL=1` on all tiers.
- [x] `qwen3-embedding:0.6b` is in the model directory of `ollama-16gib`, `ollama-48gib`, `ollama-64gib` and `ollama-48gib-slow`.
- Pending a person: after Argo CD syncs the merge and the gateway rolls onto the new config (#1929 rolls it on each config change), `uv run devops ai rag index . --force --include-kb` completes, and `kubectl -n llm exec ds/ollama-48gib -c ollama -- ollama ps` shows `qwen3-embedding:0.6b` with a context of 8192.

## Trade-offs
- The pull is a manual step on each node, as for every other model. A node that is re-created without the model fails its embedding deployment, and the router moves on to the next one.
- On `ollama-64gib`, two chat models can now stay loaded together when both fit. Each then runs at part of the GPU speed while both serve, but neither waits for the other to reload.
