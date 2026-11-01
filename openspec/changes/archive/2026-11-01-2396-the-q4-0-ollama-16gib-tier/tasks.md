# Tasks

## 1. Set q8_0 KV cache on every Ollama tier

Reads: `k8s/llm/profiles/ollama-profiles.yaml` lines 1 to 40 and 117 to 130. Changes: `k8s/llm/profiles/ollama-profiles.yaml`.

- [x] 1.1 Record the state before the change. `git grep -n "value: q4_0" -- k8s/llm/profiles/ollama-profiles.yaml` prints one line (line 126, the `ollama-16gib` container), and `git grep -h -A1 "name: OLLAMA_KV_CACHE_TYPE" -- k8s/llm/profiles/ollama-profiles.yaml | grep -c "value: q8_0"` prints 8
- [x] 1.2 In the `ollama-16gib` DaemonSet of `k8s/llm/profiles/ollama-profiles.yaml`, set the value of `OLLAMA_KV_CACHE_TYPE` to `q8_0`
- [x] 1.3 In the header comment of the same file (line 17 to 19), write that `gpt-oss:20b` took 13 GB at the context 131072 with `q4_0` KV cache (#2822), that every tier now sets `q8_0` so that every embedding vector is the same (#2396), and that `q8_0` makes the cache of that model larger by up to 1.5 GiB (an estimate, not a measurement). Keep the other sentences
- [x] 1.4 Verify the change with these commands. `git grep -n "value: q4_0" -- k8s/llm/profiles/ollama-profiles.yaml` prints nothing. `git grep -h -A1 "name: OLLAMA_KV_CACHE_TYPE" -- k8s/llm/profiles/ollama-profiles.yaml | grep -c "value: q8_0"` prints 9. `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/invariants/test_k8s_manifests.py tests/ai/test_k8s_gpu_matrix.py` passes

## Workflow follow-up

- Pending a person: after the merge, Argo CD restarts `ollama-16gib`. Confirm that the pod is Ready and that `kubectl -n llm exec ds/ollama-16gib -c ollama -- ollama ps` shows `gpt-oss:20b` and `qwen3-embedding:0.6b` at 100% GPU with the `q8_0` cache. If a model does not load on the GPU, lower `OLLAMA_CONTEXT_LENGTH` of the tier in a new item.
- Pending a person: acceptance criterion 3 of #2396. Make sure that `ollama-16gib` holds no loaded model, port-forward `ds/ollama-16gib` and `ds/ollama-48gib-slow`, send the same `/api/embed` request with three texts and `"options": {"num_ctx": 8192}` to each, and compute the cosine of each pair of vectors. Each cosine must be 0.999 or more.
