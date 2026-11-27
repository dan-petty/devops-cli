# Proposal: #5289

## Why

The Argo Workflows controller v4.1.7 manages namespace `devops`, and the `rag-ingest` manifests use fields that it does not read (#5289). CronWorkflow `rag-ingest` sets the singular field `schedule`. The controller refuses it with `SpecError` (`cron workflow must have at least one schedule`), so the RAG index does not get new content. WorkflowTemplate `rag-ingest` sets the singular field `synchronization.mutex`, which the controller does not read, so two runs can overlap. The executor of the Workflow pod has no account with a token, so it cannot write the task results. No retry rule covers exit 75, the code of this project for "try again later". The installed CRDs keep unknown fields, so the API server and Argo CD accept a singular field, and no offline check finds it before the controller log does.

## What Changes

- CronWorkflow `rag-ingest` holds its cron expression in the list `spec.schedules`. It has no `spec.schedule`.
- WorkflowTemplate `rag-ingest` holds its mutex in the list `spec.synchronization.mutexes`, with no `mutex` and no `semaphore`. It sets `spec.executor.serviceAccountName: argo-executor`. The pod keeps the account `devops-cli`, which mounts no token. The environment repository makes the account `argo-executor` and its Role. This change adds no account, no Role and no Secret.
- The template `ingest` sets a `retryStrategy` with `limit: "3"` and `expression: "asInt(lastRetry.exitCode) == 75"`. Only exit 75 retries.
- The `k8s` row of `devops ci` gets a check that runs `argo lint --offline` on the Argo objects of the rendered product base. The lint decodes each object strictly, so it fails on a singular field: `spec.schedule` of a CronWorkflow, or `synchronization.mutex` or `synchronization.semaphore` at the spec level or in a template of a Workflow spec. Each finding names the object and the field. The check reads each Argo object, not only `rag-ingest`, because the controller refuses or ignores the singular fields of each object.
- The CI jobs that run the `k8s` row, `Static Analysis` and `Fail-to-Pass Check`, copy the `argo` command of the devtools image with `.github/actions/devtools-commands`. The `devtools-bin` stage of `.devcontainer/Dockerfile` holds it. The devcontainer and the runner image already hold `argo`.
- ADR 0008 gets one Status History line in the `Fact out of date` form. Its body does not change.
- This change adds no NetworkPolicy. Policy `argo-workflow-egress` of `k8s/devops/networkpolicy.yaml` (#7364) selects each pod with the label key `workflows.argoproj.io/workflow`, so it lets the `rag-ingest` pods reach the API server on TCP 6443.
- The manifests and the `k8s` row change what the cluster runs and what CI refuses, so the change has a spec delta for `rag-ingest` and for `ci-gate-rows`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rag-ingest`: The CronWorkflow uses `schedules`, and the WorkflowTemplate uses `mutexes`, the executor account and a retry of exit 75
- `ci-gate-rows`: The `k8s` row runs the offline lint of Argo, which refuses the singular fields of the Argo objects

## Impact

- Manifests: `k8s/devops/cronworkflow-rag-ingest.yaml`, `k8s/devops/workflowtemplate-rag-ingest.yaml`
- Gate check: `tests/gate/k8s_checks/argo_workflows.py`, a new module of the `k8s` row
- CI: `.devcontainer/Dockerfile` (stage `devtools-bin`), `.github/workflows/ci.yml`, `.github/workflows/fail-to-pass.yml`
- Record: `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md` (Status History only)
- Documents: `k8s/README.md`, `docs/SERVICE_PATTERNS.md`, `docs/TESTING.md`
- The set of the new guard: `kubectl kustomize k8s/devops` renders 4 Argo objects, the CronWorkflows `infra-drift` and `rag-ingest` and the WorkflowTemplates `infra-drift` and `rag-ingest`. On the base, `argo lint --offline` names 2 fields, both of `rag-ingest`: `spec.schedule` of the CronWorkflow and `spec.synchronization.mutex` of the WorkflowTemplate. With the change, it names none.

## Feasibility

- The live controller is `quay.io/argoproj/workflow-controller:v4.1.7` with the arguments `--namespaced --managed-namespace devops` (`kubectl -n argo-workflows get deploy`, 2026-11-27). Its log holds `level=ERROR msg="invalid cron workflow" component=cron cronWorkflow=devops/rag-ingest error="cron workflow must have at least one schedule"` in each round, and `kubectl -n devops get cronworkflow rag-ingest` shows no `lastScheduledTime`.
- `kubectl auth can-i --as=system:serviceaccount:devops:argo-executor -n devops create workflowtaskresults.argoproj.io` and the same for `patch` answer `yes`. So the account exists with the Role that the executor needs.
- A test with a second controller v4.1.7 on 2026-11-26 (comment on #5289) ran a CronWorkflow with `schedules`, ran a Workflow with the singular `mutex` with no error and no lock, and took a template with `executor.serviceAccountName: argo-executor` and a pod account with no token to `Succeeded`.
- `argo` v4.1.7, the release of the controller, is in the devtools image that `.devcontainer/Dockerfile` pins (tag 1.3.2). `argo lint --offline --output simple` on the render of the base exits 1 with `in "rag-ingest" (CronWorkflow): strict decoding error: unknown field "spec.schedule"` and `in "rag-ingest" (WorkflowTemplate): strict decoding error: unknown field "spec.synchronization.mutex"`. On the render of the change it exits 0 in less than 0.1 s. It skips the objects of other groups, and it names a singular field in a template (`spec.templates[0].synchronization.mutex`) and in the `workflowSpec` of a CronWorkflow.
- `kubectl get crd cronworkflows.argoproj.io` shows `x-kubernetes-preserve-unknown-fields: true` on `spec`, and so do the CRDs of the WorkflowTemplates and the Workflows. So a schema of the installed CRDs accepts a singular field.

## Existing Tool Considered

`argo lint --offline` of Argo Workflows (Apache-2.0, maintained, the release of the controller) covers the need: it decodes each Argo object strictly and names each field that the controller does not know. The `k8s` row runs it on the render that it already makes, with no rule of our own for each field. kubeconform and kube-linter cannot refuse the fields: the installed CRDs keep unknown fields, so a schema of them accepts the fields, and kube-linter has no check of Argo fields. Argo Workflows covers the manifest fields too: `spec.schedules` of a CronWorkflow, `spec.synchronization.mutexes`, `spec.executor.serviceAccountName` and `retryStrategy.expression` of a WorkflowTemplate. The change deletes no internal code.
