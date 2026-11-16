# Tasks

## 1. Behavior

- [x] 1.1 Add `test_the_template_holds_the_doubled_attempt_limits` and update the slot-model tests in `tests/config/test_k8s_devops_runtime.py`, `tests/k8s/test_k8s_configmap.py` and `tests/roadmap/stage/test_roadmap_stage_window.py`
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/roadmap/stage/test_roadmap_stage_window.py`
- [x] 1.2 Set the doubled limits and the two local slots in `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py`

## 2. Documents

- [x] 2.1 Update the slot models in `docs/CLUSTER.md` and in the comments of the template
  - Verification: `$ uv run devops ci docs`
