# Tasks

## 1. Behavior

- [x] 1.1 Change the tests that pin the template model to `openrouter/deepseek/deepseek-v4.1-flash`
  - Verification: `$ uv run pytest tests/config/test_k8s_devops_runtime.py tests/k8s/test_k8s_configmap.py tests/roadmap/stage/test_roadmap_stage_window.py -m 'k8s or not k8s'`
- [x] 1.2 Name the new model in `ai.model`, the job tasks and the implement ladder of the template
  - Verification: `$ uv run pytest tests/config/test_k8s_devops_runtime.py tests/k8s/test_k8s_configmap.py tests/ai/benchmark/test_k8s_llm_gateway.py tests/invariants -m 'k8s or not k8s'`

## 2. Documents

- [x] 2.1 Update the template comments, the specs and docs/CLUSTER.md
  - Verification: `$ uv run devops openspec check`
