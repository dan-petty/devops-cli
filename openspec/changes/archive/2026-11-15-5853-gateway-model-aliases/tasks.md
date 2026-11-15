# Tasks

## 1. Behavior

- [x] 1.1 Add model_group_alias entries in gateway configuration
  - Verification: `$ uv run pytest tests/ai/benchmark/test_k8s_llm_gateway.py -k "test_gateway_maps_local_and_provider_model_group_aliases"`
- [x] 1.2 Verify gateway render and matrix consistency
  - Verification: `$ uv run devops ai gateway render`

## 2. Documents

- [x] 2.1 Update ai-gateway-routing spec with model alias requirements
  - Verification: `$ uv run devops openspec check`
