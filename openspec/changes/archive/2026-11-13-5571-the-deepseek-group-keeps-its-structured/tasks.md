# Tasks

## 1. Behavior

- [x] 1.1 Extend `test_the_deepseek_group_falls_back_to_the_undated_model_with_the_same_provider_filter` in `tests/ai/benchmark/test_k8s_llm_gateway.py` to assert `supports_response_schema` on both DeepSeek groups
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` fails on the base
- [x] 1.2 Set `supports_response_schema: true` on `deepseek-v4.1-flash-1017` in `k8s/llm/gateway/config.yaml`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` passes

## Criteria

- Group 1: The test fails on the base and passes with the fix.
- Pending person: After the Argo CD sync, the gateway config holds the flag on both DeepSeek groups.
