# Tasks

## 1. Behavior

- [x] 1.1 Write the manifest tests for the two orders, the router `allowed_fails`, the health-check scope and timings, the per-deployment price, and the template model; they fail on main
  - Verification: `$ uv run pytest tests/ai/benchmark/test_k8s_llm_gateway.py tests/invariants/test_k8s_manifests.py tests/ai/spend/test_hosted_group_prices.py tests/config/test_k8s_devops_runtime.py tests/k8s/test_k8s_configmap.py tests/roadmap/stage/test_roadmap_stage_window.py -m 'k8s or not k8s'`
- [x] 1.2 Give the group `deepseek-v4.1-flash-1017` two orders, set the router `allowed_fails` and the health checks, and name the group in the template again
  - Verification: `$ uv run pytest tests/ai/benchmark/test_k8s_llm_gateway.py tests/invariants/test_k8s_manifests.py tests/ai/spend/test_hosted_group_prices.py tests/config/test_k8s_devops_runtime.py tests/k8s/test_k8s_configmap.py tests/roadmap/stage/test_roadmap_stage_window.py tests/k8s/test_gateway_smoke_docs.py -m 'k8s or not k8s'`
- [x] 1.3 Prove the routing on LiteLLM 1.103.11 with a mock provider and the new config (scripts outside the repository)
  - Verification: `$ uv run --with litellm==1.103.11 python -I new_shape_router.py k8s/llm/gateway/config.yaml stall408`

## 2. Documents

- [x] 2.1 Update the YAML comments, the price comments, `k8s/README.md`, `docs/CLUSTER.md` item 19 and the specs
  - Verification: `$ uv run devops openspec check`
