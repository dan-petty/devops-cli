# Tasks

## 1. Behavior

- [x] 1.1 Write a failing test: the container `ollama` of `ollama-16gib` requests `8Gi` of memory and limits it to `8Gi`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py -k ollama_16gib_tier_limits`
- [x] 1.2 Give the container `ollama` of `ollama-16gib` in `k8s/llm/profiles/ollama-profiles.yaml` a memory limit of `8Gi`, state the reason in the header comment, and remove the stale "no memory limit" element from `test_k8s_workload_resource_limits_and_probes`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py -k workload_resource_limits`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py -k ollama_16gib_tier_limits`

## 2. Documents

- [x] 2.1 State the limit and its reason in the paragraph on `ollama-16gib` in `k8s/README.md`, GPU Placement, and in the Ollama page of the knowledge base
  - Verification: `$ uv run devops ci --check --only docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
