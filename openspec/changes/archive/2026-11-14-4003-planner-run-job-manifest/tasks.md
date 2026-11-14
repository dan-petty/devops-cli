# Tasks

## 1. Add the template and its network policy

Reads: `k8s/devops/cronjob-runner.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`, `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md`.

Changes: `k8s/devops/roadmap-service/cronjob-planner-run.yaml`, `k8s/devops/roadmap-service/networkpolicy-planner-run.yaml`, `k8s/devops/roadmap-service/kustomization.yaml`, `k8s/devops/roadmap-service/role.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`.

- [x] 1.1 Add the suspended CronJob and the deny-all NetworkPolicy, list them in the kustomization and in `deploy-stack`, and add the Role row.
  - Verification: `$ uv run python -m tests.gate.k8s`

## 2. Admit the planner shape

Reads: `k8s/devops/roadmap-service/admissionpolicy.yaml`, `src/devops_cli/k8s/cluster_job.py`, `tests/gate/k8s_checks/job_admission_policy.py`.

Changes: `k8s/devops/roadmap-service/admissionpolicy.yaml`, `src/devops_cli/k8s/cluster_job.py`, `tests/gate/k8s_checks/job_admission_policy.py`, `tests/gate/k8s_checks/runner.py`, `tests/gate/k8s_checks/telemetry_resource.py`.

- [x] 2.1 Add the planner rules to the policy and the label to `build_job`, and test the Job of the template and three refusals.
  - Verification: `$ uv run python -m tests.gate.k8s`

## 3. Document the template

Reads: `docs/CLUSTER.md`, `k8s/README.md`.

Changes: `docs/CLUSTER.md`, `k8s/README.md`.

- [x] 3.1 Add the Planner run Jobs section and the tree entry.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
