# Tasks

## 1. Behavior

- [x] 1.1 Write failing offline tests in `tests/k8s/test_k8s_doctor.py` covering `konmon check orphaned` arguments, `Deployment`/`StatefulSet`/`DaemonSet`/`CronJob` mapping (`Kind/namespace/name`), filtering out non-workload orphans, missing `konmon` on `PATH` alongside healthy `kubectl`, non-zero exit / invalid JSON error continuation, read-only arguments, and `--dry-run` plan
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_doctor.py`
- [x] 1.2 Add `BIN_KONMON`, `CONST_K8S_DOCTOR_RULE_ORPHANED_WORKLOAD`, `OrphanedWorkload`, and `konmon` collection/diagnosis in `src/devops_cli/k8s/doctor.py` and `plan_doctor_requests()`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_doctor.py`

## 2. Documents

- [x] 2.1 Update `k8s-doctor` help or docs if CLI options/behavior changed and validate OpenSpec and docs gates
  - Verification: `$ uv run devops ci docs`
