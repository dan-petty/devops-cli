# Tasks

## 1. Move the infra-drift manifests to the fields of controller v4

Kind: other. Reads: `k8s/devops/cronworkflow-infra-drift.yaml`, `k8s/devops/workflowtemplate-infra-drift.yaml`, `k8s/devops/serviceaccount.yaml`, `docs/SERVICE_PATTERNS.md`. Changes: `k8s/devops/cronworkflow-infra-drift.yaml`, `k8s/devops/workflowtemplate-infra-drift.yaml`.

- [x] 1.1 In `k8s/devops/cronworkflow-infra-drift.yaml`, replace `spec.schedule` with the list `spec.schedules` that holds the same cron expression `"0 6 * * *"`. Keep each other field
  - Verification: `$ uv run devops ci --check --only k8s` passes
- [x] 1.2 In `k8s/devops/workflowtemplate-infra-drift.yaml`, replace `spec.synchronization.mutex` with the list `spec.synchronization.mutexes` that holds the mutex `infra-drift`, and add `spec.executor.serviceAccountName: argo-executor`. Keep `serviceAccountName: devops-cli` for the pod
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. Let each Workflow pod reach the API server on TCP 6443

Kind: manifest. Reads: `k8s/devops/networkpolicy.yaml`, `k8s/devops/roadmap-service/networkpolicy-egress.yaml`, `tests/gate/k8s_checks/runner.py`, `tests/gate/k8s_checks/network_policies.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`. Changes: `k8s/devops/networkpolicy.yaml`, `tests/gate/k8s_checks/runner.py`.

- [ ] 2.1 In `tests/gate/k8s_checks/runner.py`, replace `check_only_the_service_pod_may_reach_the_api_server` with `check_only_the_service_pod_and_the_workflow_pods_may_reach_the_api_server`. It pins the selector, the types and the rules of `roadmap-service-egress` and of `argo-workflow-egress`, and it fails when another policy or the perimeter has an egress rule on TCP 6443. Replace `check_the_pods_of_jobs_carry_no_label_that_the_service_policy_selects` with `check_the_pods_of_jobs_carry_no_label_that_an_api_server_policy_selects`, which also fails on the label `workflows.argoproj.io/workflow`
  - Verification: `$ uv run devops ci --check --only k8s` fails on the base
- [ ] 2.2 Add NetworkPolicy `argo-workflow-egress` to `k8s/devops/networkpolicy.yaml`: the pod selector `matchExpressions` with the key `workflows.argoproj.io/workflow` and the operator `Exists`, the type `Egress`, and one rule for TCP 6443 to `0.0.0.0/0` with `169.254.169.254/32` excluded
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 3. Name the new policy in the documents

Kind: other. Reads: `k8s/README.md`, `docs/CLUSTER.md`, `k8s/devops/networkpolicy.yaml`. Changes: `k8s/README.md`, `docs/CLUSTER.md`.

- [ ] 3.1 In the tree of `k8s/README.md`, say that `networkpolicy.yaml` lets each Argo Workflow pod reach the API server on TCP 6443. In Runner Jobs of `docs/CLUSTER.md`, name `argo-workflow-egress` beside `roadmap-service-egress`, and say that a Job pod has no Workflow label
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: after Argo CD syncs Application `devops`, submit one Workflow from `cronwf/infra-drift` in namespace `devops`, or wait for the run of 06:00 UTC. Then `kubectl -n devops get workflow -l workflows.argoproj.io/cron-workflow=infra-drift -o jsonpath='{.items[*].status.phase}'` prints `Succeeded`.
- #5289 moves the `rag-ingest` manifests to `schedules` and `mutexes`, gives them the executor account, and adds the `k8s` row that refuses the singular fields. It adds no API server policy: `argo-workflow-egress` selects its pods.
