# Tasks

## 1. Behavior

- [x] 1.1 Write a test that fails when a gateway deployment or alias names a `:floor` route
  - Verification: `$ uv run pytest tests/ai/benchmark/test_k8s_llm_gateway.py -k floor`
- [x] 1.2 Remove `:floor` from the group, the alias and the hosted-model list
  - Verification: `$ uv run pytest tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/spend tests/config/test_k8s_devops_runtime.py tests/invariants/test_k8s_manifests.py -m 'k8s or not k8s'`

## 2. Documents

- [x] 2.1 Update the gateway comment, the pricing comment and the pricing spec example
  - Verification: `$ uv run devops openspec check`
