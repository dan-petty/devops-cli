# Tasks

## 1. Behavior

- [x] 1.1 Exclude `devops-cli-planner-run` from `devops-default-perimeter` in `k8s/devops/networkpolicy.yaml`
  - Verification: `$ uv run pytest tests/config/test_k8s_devops_runtime.py`
- [x] 1.2 Update the gate check in `tests/gate/k8s_checks/job_admission_policy.py` to assert that only the planner policy selects the planner pod
  - Verification: `$ uv run python -c "from tests.gate.k8s_checks import job_admission_policy as m; m.check_the_planner_template_has_the_controls_of_adr_0018()"`

## 2. Documents

- [x] 2.1 Update the comments in `networkpolicy.yaml` and `networkpolicy-planner-run.yaml`, and update `k8s/README.md`
  - Verification: `$ uv run devops ci docs`
