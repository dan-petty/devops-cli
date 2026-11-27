# Proposal: #7364

## Why

The Argo Workflows controller v4.1.7 manages namespace `devops`, and the `infra-drift` manifests use fields that it does not read (#7364). CronWorkflow `infra-drift` sets the singular field `schedule`. The controller refuses it with `SpecError` (`cron workflow must have at least one schedule`), so the daily drift check does not run. WorkflowTemplate `infra-drift` sets the singular field `synchronization.mutex`, which the controller does not read, so the mutex does not hold. The executor of the Workflow pod has no account with a token, and no NetworkPolicy of `devops` lets a Workflow pod reach the API server. So the executor cannot write the task results, and each Workflow in `devops` ends in `Error`.

## What Changes

- CronWorkflow `infra-drift` holds its cron expression in the list `spec.schedules`. It has no `spec.schedule`.
- WorkflowTemplate `infra-drift` holds its mutex in the list `spec.synchronization.mutexes`. It sets `spec.executor.serviceAccountName: argo-executor`. The pod keeps the account `devops-cli`, which mounts no token. The environment repository makes the account `argo-executor` and its Role. This change adds no account, no Role and no Secret.
- A new NetworkPolicy `argo-workflow-egress` in `k8s/devops/networkpolicy.yaml` selects each pod with the label key `workflows.argoproj.io/workflow`. It lets the pod reach the API server on TCP 6443 only, with the peer of `roadmap-service-egress`. The rule also covers `rag-ingest` and each later WorkflowTemplate, so #5289 adds no policy of its own.
- The gate check of the `k8s` row that pinned the one policy with TCP 6443 now pins the two policies, and it refuses each other policy with TCP 6443. The Job pod templates carry no Workflow label, so the new policy does not select a Job pod.
- The manifests and a gate check change what the cluster runs, so the change has a spec delta for `infra-drift` and for `k8s-network-policies`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `infra-drift`: The CronWorkflow uses `schedules`, and the WorkflowTemplate uses `mutexes` and the executor account
- `k8s-network-policies`: The Argo Workflow pods reach the API server on TCP 6443 only

## Impact

- Manifests: `k8s/devops/cronworkflow-infra-drift.yaml`, `k8s/devops/workflowtemplate-infra-drift.yaml`, `k8s/devops/networkpolicy.yaml`
- Gate check: `tests/gate/k8s_checks/runner.py`
- Documents: `k8s/README.md`, `docs/CLUSTER.md`
- The set of NetworkPolicies with egress on TCP 6443: `kubectl kustomize k8s/devops` renders 1 such policy on the base (`roadmap-service-egress`) and 2 with the change. Both select by label, and no Job pod template carries either label.

## Feasibility

- The live controller is `quay.io/argoproj/workflow-controller:v4.1.7` with `--namespaced --managed-namespace devops` (`kubectl -n argo-workflows get deploy`). Its log on 2026-11-27 holds `level=ERROR msg="invalid cron workflow" cronWorkflow=devops/infra-drift error="cron workflow must have at least one schedule"` every 20 minutes, and no `infra-drift` Workflow exists.
- `kubectl auth can-i --as=system:serviceaccount:devops:argo-executor -n devops create workflowtaskresults.argoproj.io` and the same for `patch` answer `yes`, and `get secrets` answers `no`. So the account exists with the Role that the executor needs, and with no read of a Secret.
- The endpoint of Service `kubernetes` listens on port 6443. A test Workflow in `devops` with `executor.serviceAccountName: argo-executor` ran its `main` container, and its `wait` container then failed with `dial tcp <cluster address>:443: connect: connection refused` when it posted the `workflowtaskresults` (comment of 2026-11-27 on #7364). In `devops`, only `roadmap-service-egress` allowed TCP 6443.
- The installed Argo CRDs keep unknown fields (`x-kubernetes-preserve-unknown-fields: true` on `spec`), so the API server accepts a singular field that the controller then refuses or ignores.

## Existing Tool Considered

Argo Workflows covers the need with its own fields: `spec.schedules` of a CronWorkflow, `spec.synchronization.mutexes` and `spec.executor.serviceAccountName` of a WorkflowTemplate. Kubernetes NetworkPolicy covers the API server egress. The change writes no new code, so it has no build cost. It deletes no internal code.
