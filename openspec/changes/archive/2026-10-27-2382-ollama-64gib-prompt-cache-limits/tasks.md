# Tasks

## 1. Bound prompt cache and set memory limit on ollama-64gib

- [x] Write failing regression test in `tests/test_k8s_llm_gateway.py` asserting `LLAMA_ARG_CACHE_RAM: "4096"` and `limits.memory: 12Gi` on `ollama-64gib` (`uv run pytest tests/test_k8s_llm_gateway.py -k test_ollama_64gib_tier_constrains_prompt_cache_and_memory_limit`).
- [x] Add `LLAMA_ARG_CACHE_RAM: "4096"` and `limits.memory: 12Gi` to the `ollama-64gib` DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml` (`uv run pytest tests/test_k8s_llm_gateway.py -k test_ollama_64gib_tier_constrains_prompt_cache_and_memory_limit`).
- [x] Document prompt cache sizing and memory constraints in `k8s/llm/profiles/ollama-profiles.yaml` and `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md` (`uv run devops docs generate --sync-readme`).
- [x] Verify test suite passes (`uv run pytest tests/test_k8s_llm_gateway.py tests/test_k8s.py`).

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
