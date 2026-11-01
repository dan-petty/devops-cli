# Tasks

## 1. Set q8_0 KV cache on ollama-16gib

Reads: none. Changes: `k8s/llm/profiles/ollama-profiles.yaml`.

- [ ] 1.1 Write a test that parses k8s/llm/profiles/ollama-profiles.yaml, iterates every DaemonSet container env block, and asserts that every OLLAMA_KV_CACHE_TYPE value is q8_0. The test fails before the change because ollama-16gib holds q4_0, and verify that `uv run devops ci test tests/test_ollama_profiles.py` fails on the base
- [ ] 1.2 In k8s/llm/profiles/ollama-profiles.yaml, change the OLLAMA_KV_CACHE_TYPE value from q4_0 to q8_0 in the ollama-16gib container env block. Update the file header comment that says 'which takes 13 GB with q4_0 KV cache' to say 'which takes 13 GB with q4_0 KV cache (now q8_0)' or simply change the reference to q8_0, and verify that `uv run devops ci test tests/test_ollama_profiles.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
