# Tasks

## 1. Version Skew Detection and Diagnostics

- [x] 1.1 Write failing tests for version skew diagnostics and deploy-stack skew warnings, verifying failure with `uv run devops ci test tests/test_k8s_doctor.py`
- [x] 1.2 Implement `Snapshot.server_version`, `get_code` in `plan_doctor_requests`, and the version skew diagnostic rule in `src/devops_cli/k8s/doctor.py` and `src/devops_cli/k8s/service.py`, verifying with `uv run devops ci test tests/test_k8s_doctor.py`
- [x] 1.3 Add kubectl version skew warning to `src/devops_cli/commands/k8s/stack_lifecycle.py` before applying stack resources, verifying with `uv run devops ci test tests/test_k8s_stack_lifecycle.py`
- [x] 1.4 Document the kubectl version skew policy and homelab cluster status in `k8s/README.md`, and synchronize documentation with `uv run devops docs generate --sync-readme`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
