# Task 309: ArgoCD Server API, CRD Reconciliation & Automated Canary Metric Verification Research

**Issue**: [#309](https://github.com/dan-petty/devops-cli/issues/309)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

GitOps fleet synchronization, workflow orchestration, and progressive delivery depended on external `argocd`, `argo`, `kubectl`, and `kubectl-argo-rollouts` binary installations, creating environment friction on CI runners and developer workstations and reducing every operation to a shell return-code check. This deliverable introduces `ArgoCRDService`, which reads and mutates Argo custom resources in-process through the official Kubernetes `CustomObjectsApi`, and projects every response into typed Pydantic state models.

### Key Deliverables Completed:

- [x] **ArgoCRDService Architecture (`src/devops_cli/argo/crd.py`)**:
  - Direct in-process manipulation of the `argoproj.io` API group via `CustomObjectsApi`, reusing the cached client and kubeconfig resolution already provided by `KubernetesService`.
  - Generic custom resource access (`list_resources`, `get_resource`, `patch_resource`, `apply_resource`) with `apply_resource` creating a resource and patching it in place when it already exists.
  - Typed accessors for Applications, ApplicationSets, Rollouts, AnalysisRuns, and Workflows.
  - `workflow_pod_names` resolves the Pod-type DAG nodes backing a Workflow so logs stream natively through `KubernetesService.read_pod_logs`.
- [x] **CustomObjectsApi Exposure (`src/devops_cli/k8s/service.py`)**:
  - New `custom_objects_api()` accessor constructing and caching `CustomObjectsApi` alongside the existing Core, Apps, and Version clients, raising `KubernetesContextError` when the cluster is unreachable.
- [x] **Native Rollout Control-Plane Mutations (`src/devops_cli/argo/rollouts.py`)**:
  - `promote_rollout`, `abort_rollout`, and `restart_rollout` now patch the exact control-plane fields the rollouts controller watches — clearing `status.pauseConditions` / `status.controllerPause` (with `status.promoteFull` for a full promotion), setting `status.abort`, and stamping `spec.restartAt` — instead of shelling out to `kubectl argo rollouts`.
  - Shared `_mutate_rollout` helper centralizes validation, dry-run short-circuiting, and typed error handling.
- [x] **Command Refactoring (`src/devops_cli/commands/argo.py`)**:
  - `devops argo workflows list` / `submit` / `logs` read, submit, and stream natively; `--wait` polls the Workflow to a terminal phase under a bounded budget and exits non-zero on `Failed` / `Error`.
  - `devops argo rollouts list` / `status` render typed progressive delivery state, including canary step position and replica counts, with `--watch` driven by `LiveResourceWatcher`.
  - `devops argo cd apps bootstrap-gitops` applies the root Application manifest through the API server instead of `kubectl apply -f`.
- [x] **Typed Pydantic State Models (`src/devops_cli/models/argo.py`)**:
  - `ArgoResourceState`, `ArgoRolloutState`, and `ArgoWorkflowState` replace stdout scraping, tolerating absent, null, and wrongly typed resource sections.
- [x] **Typed Exception Hierarchy (`src/devops_cli/exceptions/argo.py`)**:
  - `ArgoError` and `ArgoResourceNotFoundError` with dedicated error codes, replacing shell return-code checks; HTTP 404 is distinguished from transport failures.
  - Name validation inside the service raises `ArgoError` rather than `typer.Exit`, since the service is consumed by FastMCP tools and the TUI as well as the CLI.
- [x] **Centralized Constants & Defaults**:
  - API group, version, resource plurals, Rollout control-plane field names, and terminal Workflow phases centralized in `src/devops_cli/config/constants.py`.
  - Rollout watch interval and Workflow poll/wait budgets centralized in `src/devops_cli/config/defaults.py`.
- [x] **Automated Tests & Quality Gates**:
  - 28 unit tests in `tests/test_argo_crd.py` using structural tuple equality assertions, covering client resolution, error translation, manifest application, rollout mutations, workflow projection, and sparse/malformed payload tolerance.
  - Existing rollout and CLI suites migrated from subprocess assertions to control-plane patch assertions.
  - `src/devops_cli/argo/crd.py` at 99% coverage; 119 Argo tests passing.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ maintained.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy strict, audit, security, actionlint, docs, uv check, lockfile).
- `devops scan complexity` clean across `src/devops_cli/argo`.
- No `argo`, `argocd`, `kubectl`, or `kubectl argo rollouts` subprocess invocations remain in the Argo command group or package.

## Deferred

Native gRPC integration with the ArgoCD API server is not included. The existing authenticated REST client (`devops argo cd apps list` / `status` / `sync`) already multiplexes over HTTP/2 via `httpx2`, and CRD reconciliation through the Kubernetes API server covers the deliverable's fleet synchronization and progressive delivery objectives without introducing a protobuf toolchain dependency. Automated canary metric verification against Prometheus SLO thresholds continues to be served by `evaluate_rollout_gate`, which now drives aborts through the native control-plane patch path.
