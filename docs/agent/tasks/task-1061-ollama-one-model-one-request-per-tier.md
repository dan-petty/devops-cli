# Task: Every Ollama Tier Keeps One Model Loaded and Serves One Request at a Time (#1061)

**Issue**: [#1061](https://github.com/dan-petty/devops-cli/issues/1061)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Ollama reserves KV cache for `OLLAMA_CONTEXT_LENGTH` × `OLLAMA_NUM_PARALLEL` tokens and keeps up to `OLLAMA_MAX_LOADED_MODELS` models resident. With four slots and contexts of 48k to 256k tokens, a dense ~30B model did not fit. Review session `20261003-051015` (gemma4:31b) completed no model call in 25 minutes:
- ollama-48gib-slow reserved `n_ctx = 512000` (4 × 128000), offloaded 44 of 61 layers, and failed with `failed to create MTP context`, returning a 500 after 3 to 4 minutes of load attempts.
- ollama-48gib failed the same way once its node returned.
- ollama-64gib answered after 18 to 25 minutes per call, past the client's 1,200 s read timeout.

The owner set both values to 1 on every tier.

## Key Changes
- **`k8s/llm/profiles/ollama-profiles.yaml`**: `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` are `"1"` on all nine DaemonSets: 16gib, 24gib, 32gib, 48gib, 48gib-slow, 64gib, 72gib, 96gib and 128gib. A header comment gives the reason. Each tier keeps its `OLLAMA_CONTEXT_LENGTH`.
- **`tests/test_k8s_llm_gateway.py`**: `test_every_ollama_tier_keeps_one_model_and_serves_one_request` reads every DaemonSet in the manifest and requires both values to be `"1"`.

## Acceptance Criteria
- [x] Every Ollama DaemonSet sets `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` to `"1"`.
- [x] The offline test fails on the previous manifest, where 16gib had 2 and 2 and the other tiers had 2 and 4, and passes now.
- [x] `uv run devops ci` passes.
- Pending a person: after `kubectl apply -k k8s/llm/profiles`, each tier's Ollama log shows the loaded model's `n_ctx` equal to its `OLLAMA_CONTEXT_LENGTH`, and gemma4:31b loads on ollama-48gib-slow without `failed to create MTP context`.

## Trade-offs
- Requests to a busy tier queue in Ollama. Queue time counts toward the client's 1,200 s read timeout and the gateway's 1,500 s timeout, and mixture-of-experts models such as qwen3-coder:30b lose the throughput that batching four sequences gave.
- A tier serving both an embedding model and a chat model unloads one to load the other: ollama-48gib-slow, and ollama-16gib when its embedding deployments return. Embedding placement and per-deployment concurrency belong to the gateway's health-check routing item.
