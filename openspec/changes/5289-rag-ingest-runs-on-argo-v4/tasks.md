# Tasks

## 1. Refuse the singular Argo fields in the k8s row

Kind: other. Reads: `tests/gate/k8s.py`, `tests/gate/k8s_render.py`, `tests/gate/k8s_checks/network_policies.py`, `tests/gate/k8s_checks/rag_ingest.py`. Changes: `tests/gate/k8s_checks/argo_workflows.py`.

- [x] 1.1 In `tests/gate/k8s_checks/argo_workflows.py`, add the cases that give the rule `singular_field_problems` one small Argo object for each singular field: `spec.schedule` of a CronWorkflow, `spec.synchronization.mutex` and `spec.templates[main].synchronization.mutex` of a WorkflowTemplate, `spec.synchronization.semaphore` of a Workflow and `spec.workflowSpec.synchronization.semaphore` of a CronWorkflow. Each case expects one finding that names the field. Add the case that gives the rule the plural fields and a CronJob with `spec.schedule`, and expects no finding. Run the cases before the rule exists, and see them fail
  - Verification: `$ uv run devops ci --check --only k8s` fails on the new cases
- [x] 1.2 Add the rule `singular_field_problems`. It reads each object whose `apiVersion` starts with `argoproj.io/`, and gives one line for each singular field, with the kind, the namespace, the name, the path of the field and the plural field to use
  - Verification: `$ uv run devops ci --check --only k8s` passes the cases of the rule
- [x] 1.3 Add the check `check_no_argo_object_of_the_product_base_sets_a_singular_field`, which gives the rule each object of `applied_documents(DEVOPS_DIR)`
  - Verification: `$ uv run devops ci --check --only k8s` fails on the base, and names `spec.schedule` of CronWorkflow `devops/rag-ingest` and `spec.synchronization.mutex` of WorkflowTemplate `devops/rag-ingest`

## 2. Move the rag-ingest manifests to the fields of controller v4

Kind: other. Reads: `k8s/devops/workflowtemplate-infra-drift.yaml`, `k8s/devops/networkpolicy.yaml`, `docs/SERVICE_PATTERNS.md`. Changes: `k8s/devops/cronworkflow-rag-ingest.yaml`, `k8s/devops/workflowtemplate-rag-ingest.yaml`.

- [ ] 2.1 In `k8s/devops/cronworkflow-rag-ingest.yaml`, replace `spec.schedule` with the list `spec.schedules` that holds the same cron expression `"*/3 * * * *"`. Keep each other field, and add no `suspend`
  - Verification: `$ uv run devops ci --check --only k8s` no longer names CronWorkflow `devops/rag-ingest`
- [ ] 2.2 In `k8s/devops/workflowtemplate-rag-ingest.yaml`, replace `spec.synchronization.mutex` with the list `spec.synchronization.mutexes` that holds the mutex `rag-ingest`, and add `spec.executor.serviceAccountName: argo-executor`. Keep `serviceAccountName: devops-cli` for the pod
  - Verification: `$ uv run devops ci --check --only k8s` passes
- [ ] 2.3 In the template `ingest` of `k8s/devops/workflowtemplate-rag-ingest.yaml`, add `retryStrategy` with `limit: "3"` and `expression: "asInt(lastRetry.exitCode) == 75"`
  - Verification: `$ uv run devops ci --check --only k8s,kube-linter` passes

## 3. Record the stale controller facts in ADR 0008

Kind: other. Reads: `docs/adr/README.md`, `tests/invariants/test_adr_records.py`. Changes: `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md`.

- [ ] 3.1 At the end of the Status History section of ADR 0008, add one dated line in the `Fact out of date` form, 30 words or fewer: the controller runs namespaced in `devops`, and the manifests use `schedules` and `mutexes`. Do not edit the body
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py` passes

## 4. Name the rule of the Argo fields in the documents

Kind: other. Reads: `k8s/README.md`, `tests/gate/k8s_checks/argo_workflows.py`. Changes: `k8s/README.md`.

- [ ] 4.1 In `k8s/README.md`, add the section Argo Workflows after the section NetworkPolicy. It says that each Argo object of `k8s/devops` uses `schedules`, `mutexes` and `semaphores`, and that the `k8s` row refuses the singular fields
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: after this change releases and Argo CD syncs Application `devops`, wait for the next run of `cronwf/rag-ingest` in namespace `devops`. Then `kubectl -n devops get workflow -l workflows.argoproj.io/cron-workflow=rag-ingest -o jsonpath='{.items[*].status.phase}'` prints `Succeeded`.
