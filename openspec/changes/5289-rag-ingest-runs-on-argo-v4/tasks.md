# Tasks

## 1. Refuse the singular Argo fields in the k8s row

Kind: other. Reads: `tests/gate/k8s.py`, `tests/gate/k8s_render.py`, `tests/gate/k8s_checks/network_policies.py`, `tests/gate/k8s_checks/rag_ingest.py`. Changes: `tests/gate/k8s_checks/argo_workflows.py`.

- [x] 1.1 In `tests/gate/k8s_checks/argo_workflows.py`, add the cases that give the function `argo_lint_problems` small Argo objects in memory with one singular field each: `spec.schedule` of a CronWorkflow, `spec.synchronization.mutex` and `spec.templates[0].synchronization.mutex` of a WorkflowTemplate, `spec.synchronization.semaphore` of a Workflow and `spec.workflowSpec.synchronization.semaphore` of a CronWorkflow. Each case expects one finding that names the object and the field. Add the case that gives the function the plural fields and a CronJob with `spec.schedule`, and expects no finding. Run the cases before the function exists, and see them fail
  - Verification: `$ uv run devops ci --check --only k8s` fails on the new cases
- [x] 1.2 Add the function `argo_lint_problems`. It writes the objects to a file in a temporary folder, runs `argo lint --offline --output simple` on it, and returns one line for each problem, or the output of a lint that fails with no such line
  - Verification: `$ uv run devops ci --check --only k8s` passes the cases of the function
- [x] 1.3 Add the check `check_each_argo_object_of_the_product_base_passes_the_offline_lint`, which gives the function each object of `applied_documents(DEVOPS_DIR)`
  - Verification: `$ uv run devops ci --check --only k8s` fails on the base, and names `spec.schedule` of CronWorkflow `rag-ingest` and `spec.synchronization.mutex` of WorkflowTemplate `rag-ingest`

## 2. Give the CI jobs of the k8s row the argo command

Kind: other. Reads: `.github/actions/devtools-commands/action.yml`, `docs/SDLC.md`. Changes: `.devcontainer/Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/fail-to-pass.yml`.

- [x] 2.1 Add `/usr/local/bin/argo` to the stage `devtools-bin` of `.devcontainer/Dockerfile`. Add `argo` to the commands that `Static Analysis` of `.github/workflows/ci.yml` copies. In `.github/workflows/fail-to-pass.yml`, copy `argo` with `.github/actions/devtools-commands` and put its folder on PATH before the replay
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor,hadolint` passes

## 3. Move the rag-ingest manifests to the fields of controller v4

Kind: other. Reads: `k8s/devops/workflowtemplate-infra-drift.yaml`, `k8s/devops/networkpolicy.yaml`, `docs/SERVICE_PATTERNS.md`. Changes: `k8s/devops/cronworkflow-rag-ingest.yaml`, `k8s/devops/workflowtemplate-rag-ingest.yaml`.

- [ ] 3.1 In `k8s/devops/cronworkflow-rag-ingest.yaml`, replace `spec.schedule` with the list `spec.schedules` that holds the same cron expression `"*/3 * * * *"`. Keep each other field, and add no `suspend`
  - Verification: `$ uv run devops ci --check --only k8s` no longer names CronWorkflow `rag-ingest`
- [ ] 3.2 In `k8s/devops/workflowtemplate-rag-ingest.yaml`, replace `spec.synchronization.mutex` with the list `spec.synchronization.mutexes` that holds the mutex `rag-ingest`, and add `spec.executor.serviceAccountName: argo-executor`. Keep `serviceAccountName: devops-cli` for the pod
  - Verification: `$ uv run devops ci --check --only k8s` passes
- [ ] 3.3 In the template `ingest` of `k8s/devops/workflowtemplate-rag-ingest.yaml`, add `retryStrategy` with `limit: "3"` and `expression: "asInt(lastRetry.exitCode) == 75"`
  - Verification: `$ uv run devops ci --check --only k8s,kube-linter` passes

## 4. Record the stale controller facts in ADR 0008

Kind: other. Reads: `docs/adr/README.md`, `tests/invariants/test_adr_records.py`. Changes: `docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md`.

- [ ] 4.1 At the end of the Status History section of ADR 0008, add one dated line in the `Fact out of date` form, 30 words or fewer: the controller runs namespaced in `devops`, and the manifests use `schedules` and `mutexes`. Do not edit the body
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py` passes

## 5. Name the offline lint of Argo in the documents

Kind: other. Reads: `tests/gate/k8s_checks/argo_workflows.py`. Changes: `k8s/README.md`, `docs/SERVICE_PATTERNS.md`, `docs/TESTING.md`.

- [ ] 5.1 In `k8s/README.md`, add the section Argo Workflows after the section NetworkPolicy. It says that each Argo object of `k8s/devops` uses `schedules`, `mutexes` and `semaphores`, and that the `k8s` row runs `argo lint --offline` on the Argo objects. Name `argo lint --offline` in the tools of CT2 in `docs/SERVICE_PATTERNS.md` and in the schema and policy tools of CI in `docs/TESTING.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: after this change releases and Argo CD syncs Application `devops`, wait for the next run of `cronwf/rag-ingest` in namespace `devops`. Then `kubectl -n devops get workflow -l workflows.argoproj.io/cron-workflow=rag-ingest -o jsonpath='{.items[*].status.phase}'` prints `Succeeded`.
