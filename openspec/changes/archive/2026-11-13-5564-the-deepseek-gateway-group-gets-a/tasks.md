# Tasks

## 1. Behavior

- [x] 1.1 Add `deepseek-v4.1-flash` to `HOSTED_GROUPS`, add the fallback rule to `test_gateway_configmap_virtual_models`, and add `test_the_deepseek_group_falls_back_to_the_undated_model_with_the_same_provider_filter` in `tests/ai/benchmark/test_k8s_llm_gateway.py`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` fails on the base
- [x] 1.2 Add the group and the fallback to `k8s/llm/gateway/config.yaml`, the price to `_HOSTED_GROUP_PRICES` in `src/devops_cli/ai/spend/pricing.py`, and the group to `CONST_AI_GATEWAY_HOSTED_MODELS` in `src/devops_cli/config/constants.py`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/spend/test_hosted_group_prices.py` passes

## 2. Documents

- [x] 2.1 Name the new group and the second fallback in SECURITY.md item 13 and in the hosted-model text of `k8s/README.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: The gateway config test proves the fallback, the hosted group and the same provider filter.
- Group 1: `tests/ai/spend/test_hosted_group_prices.py` passes with the new group.
- Pending person: After the Argo CD sync, a call that names `deepseek-v4.1-flash` answers, and a failed call of `deepseek-v4.1-flash-1017` falls back, as the gateway log or its fallback counter shows.
