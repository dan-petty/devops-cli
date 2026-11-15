# Tasks

## 1. Behavior

- [x] 1.1 Update `k8s/devops/configmap.example.yaml` to use prefixed model names
  - Verification: `$ uv run pytest tests/config/test_k8s_devops_runtime.py`
- [x] 1.2 Update `k8s/llm/values-open-webui.yaml` and `k8s/monitoring/grafana-values.yaml`
  - Verification: `$ uv run pytest tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 1.3 Update test invariants in `tests/config/test_k8s_devops_runtime.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`, `tests/ai/spend/test_hosted_group_prices.py`, and `tests/k8s/test_k8s_configmap.py`
  - Verification: `$ uv run pytest tests/config/test_k8s_devops_runtime.py tests/ai/benchmark/test_k8s_llm_gateway.py tests/roadmap/stage/test_roadmap_stage_window.py tests/ai/spend/test_hosted_group_prices.py tests/k8s/test_k8s_configmap.py`

## 2. Documents

- [x] 2.1 Update `docs/CLUSTER.md`, `docs/roadmap/implement.md`, and `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Validate OpenSpec change
  - Verification: `$ uv run devops openspec check`
