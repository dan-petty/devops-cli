# Proposal

## Why

Issue #2396: `ollama-16gib` sets `OLLAMA_KV_CACHE_TYPE` to `q4_0`, and the other eight Ollama tiers set `q8_0`. Ollama passes the value to `llama-server` for every model, also for the embedding model. The 4-bit KV cache changes the vectors of `qwen3-embedding:0.6b`: for the same input, a vector from `ollama-16gib` has a cosine of 0.78 to 0.92 against a vector from a `q8_0` tier. The gateway lists `ollama-16gib-fast` as an `order: 2` deployment of that model. When an order 1 tier fails or cools down, a RAG batch goes to it, and its drifted vectors go into the Qdrant collection that holds the `q8_0` vectors.

## What Changes

- `OLLAMA_KV_CACHE_TYPE` of the `ollama-16gib` DaemonSet goes from `q4_0` to `q8_0` in `k8s/llm/profiles/ollama-profiles.yaml`. All nine tiers then set `q8_0`.
- The header comment of that file says that the 13 GB figure of `gpt-oss:20b` was measured with `q4_0`, and that `q8_0` makes the cache larger by up to 1.5 GiB. The new figure is an estimate, not a measurement.
- The change adds the requirement `Every Ollama tier sets one KV cache type` to the capability `ai-gateway-routing`. A manifest is observable, so the change carries a delta.
- The change adds no test and no code. A manifest value is not new code, so a command checks it (task 1.4). The reason is in `design.md`.
- The change records no tier of origin in Qdrant. The issue scopes that out.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: adds the requirement `Every Ollama tier sets one KV cache type`.

## Impact

- Cluster: the DaemonSet `ollama-16gib` restarts when Argo CD syncs. The model on hawk reloads with the larger cache.
- Code and tests: none change.
- Existing tests that read `k8s/llm/profiles/ollama-profiles.yaml` must stay green: `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/invariants/test_k8s_manifests.py` and `tests/ai/test_k8s_gpu_matrix.py`. Task 1.4 runs them.

## Acceptance

- Criterion 1 (`ollama-16gib` sets `q8_0`): group 1, task 1.2.
- Criterion 2 (all nine tiers set the same value): group 1, task 1.4, which counts nine `q8_0` values and no `q4_0` value.
- Criterion 3 (the same `/api/embed` request to `ollama-16gib` and `ollama-48gib-slow` gives a cosine of 0.999 or more): pending a person. The check needs a port-forward to the live DaemonSets after Argo CD rolls out the manifest. The first step of "Workflow follow-up" in `tasks.md` names it.

## Feasibility

All commands ran on 2026-11-01 on `origin/main` at `1c20865a`.

The mechanism of the issue:

- `git grep -n -A1 "name: OLLAMA_KV_CACHE_TYPE" -- k8s/llm/profiles/ollama-profiles.yaml` shows nine values: `q4_0` at line 126 (`ollama-16gib`) and `q8_0` at lines 271, 411, 558, 707, 851, 997, 1149 and 1291. The nine DaemonSets are 16gib, 24gib, 32gib, 48gib, 48gib-slow, 64gib, 72gib, 96gib and 128gib.
- `grep -n -B1 -A6 "qwen3-embedding" k8s/llm/gateway/config.yaml` shows `ollama-16gib-fast` at `order: 2` (line 68), with `num_ctx: 8192`. `ollama-48gib-slow` is also `order: 2` (line 79). `ollama-48gib-fast` and `ollama-64gib-standard` are `order: 1`.
- The vector drift is the measurement in the issue (Ollama 0.34.4, cosines of 0.858, 0.922 and 0.784). I did not repeat it: the kubelet of node hawk gave a 502 for `kubectl -n llm exec ds/ollama-16gib -c ollama -- ollama ps` and for `kubectl -n llm port-forward`, so no pod on that node could be reached today. Criterion 3 covers the repeat after the rollout.

Nothing newer did or removed this:

- `git log --oneline -8 origin/main -- k8s/llm/profiles/ollama-profiles.yaml` shows no commit that touches the KV cache type. The last two (`325fbdbd`, #2824, and `305d3ba0`) change the context length and a token mount.
- `git grep -l -i "16gib\|KV_CACHE" origin/main -- openspec/changes` outside the archive and this folder finds no active change. The archived change `2395-ollama-0-40-12` leaves this fix to #2396 in its design ("Set one KV cache type on every tier that embeds" is rejected there for this reason).
- #2027, the related item that intake names, is closed. It spread embeddings over order 1 tiers and does not set a KV cache type.

The issue text says that the context of the tier is 48000. That is wrong. `OLLAMA_CONTEXT_LENGTH` of `ollama-16gib` is `"131072"` at line 120, since #2824 (merged 2026-10-31). The header of the manifest records that `gpt-oss:20b` takes 13 GB at that length with `q4_0`. The earlier plan did not check that `q8_0` fits. The check:

- Node hawk has one RTX 5070 Ti: `kubectl get node hawk` shows `nvidia.com/gpu.vram=16303MiB`.
- The query `max_over_time(DCGM_FI_DEV_FB_USED[3d])` on the cluster Prometheus gives a peak of 13660 MiB for hawk. That is the `q4_0` state with `gpt-oss:20b` at 131072.
- The architecture from `config.json` of `openai/gpt-oss-20b`: 24 layers, 8 KV heads, head dimension 64, a sliding window of 128, and 12 `full_attention` layers.
- The size of the cache is `2 x 8 x 64 x layers x 131072` elements. A `q4_0` element takes 18/32 byte and a `q8_0` element takes 34/32 byte. With the 12 full layers, the cache grows from 864 MiB to 1632 MiB: 768 MiB more. If all 24 layers keep a full cache, it grows from 1728 MiB to 3264 MiB: 1536 MiB more.
- The peak of 13660 MiB is the chat model alone. The archived change 2822 measured `gpt-oss:20b` alone at 13 GB. The 3-day median is 23 MiB, so the GPU is mostly idle.
- The bound for the chat model alone is 13660 + up to 1536 = 15196 MiB of 16303 MiB. About 1100 MiB stay free in the worst case. In the likely case (768 MiB more) about 1870 MiB stay free.
- The embedder `qwen3-embedding:0.6b` at `num_ctx` 8192 is not counted. `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md` (line 98) says it needs 2.2 to 2.9 GB, and that Ollama unloads the idle model when both do not fit. The change to `q8_0` does not alter this rule. The embedder cache grows by about 225 MiB (an estimate from its published architecture: 28 layers, 8 KV heads, head dimension 128), but the chat model and the embedder are not proven to be resident together.
- The change fits for the chat model alone, with a small margin in the worst case.

The margin is an estimate. The first "Workflow follow-up" step makes a person confirm it with `ollama ps` after the rollout. If the model no longer loads 100% on the GPU, the person lowers `OLLAMA_CONTEXT_LENGTH` of the tier in a new item. This plan makes no such decision.

## Existing Tool Considered

The change edits a Kubernetes manifest and builds nothing. Argo CD, which already tracks `main`, applies it. The repeatable checks use `git grep` and the existing manifest tests, which parse the file with PyYAML. No new tool or library is needed.
