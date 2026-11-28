# Tasks

## 1. Refuse app.kubernetes.io/component: project-review on non-stage Service Jobs

Kind: behavior.

Reads: `k8s/devops/roadmap-service/admissionpolicy.yaml`, `tests/gate/k8s_checks/job_admission_policy.py`.

Changes: `k8s/devops/roadmap-service/admissionpolicy.yaml`, `tests/gate/k8s_checks/job_admission_policy.py`.

- [x] 1.1 Write failing checks in `tests/gate/k8s_checks/job_admission_policy.py` verifying that a non-stage Service Job with `app.kubernetes.io/component: project-review` is refused by the label rule, while stage Jobs and implement Jobs (with `roadmap-implement` or no component label) remain admitted.
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Add the `project-review` refusal conjunct and message update to `k8s/devops/roadmap-service/admissionpolicy.yaml`.
  - Verification: `$ uv run devops ci --check --only k8s`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
