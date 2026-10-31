# Design: Dry-Run Classification for Argo Commands

## Context
Commands in `argo` handle Argo CD applications, fleet synchronization, GitOps drift detection, progressive delivery Rollouts, and Argo Workflows. In a dry run, any command that communicates with an external cluster, Argo CD REST API, Prometheus, or subprocess must return a plan of its intended actions rather than executing requests or returning mock echo responses. Commands that perform purely local work without network or cluster interaction are classified as `no-external-request`.

## Technical Strategy
1. **Planned Request Construction**:
   Create `src/devops_cli/argo/argo_plans.py` containing dedicated plan builders for the 20 external-request commands:
   - For commands reaching Argo CD HTTP API, generate the token request (`POST <base>/api/v1/session`) before the target action request.
   - `plan_argocd_apps_list`: lists token mint request and application list endpoint request.
   - `plan_argocd_apps_status`: lists token mint request and application status endpoint request.
   - `plan_argocd_apps_sync`: lists token mint request and application sync endpoint request.
   - `plan_argocd_bootstrap_gitops`: lists Kubernetes CustomObjectsApi application creation request.
   - `plan_argo_fleet_sync`: lists token mint request and per-cluster sync requests.
   - `plan_argo_gitops_sync`: lists token mint request and API/webhook sync request.
   - `plan_argo_gitops_watch`: lists token mint request and drift check / sync requests.
   - `plan_argo_rollouts_abort`: lists Kubernetes Rollout abort patch request.
   - `plan_argo_rollouts_analyze`: lists Prometheus metric query and optional Rollout abort patch request.
   - `plan_argo_rollouts_list`: lists Kubernetes Rollout listing request.
   - `plan_argo_rollouts_promote`: lists Kubernetes Rollout promotion patch request.
   - `plan_argo_rollouts_restart`: lists Kubernetes Rollout restart patch request.
   - `plan_argo_rollouts_status`: lists Kubernetes Rollout retrieval request.
   - `plan_argo_workflows_list`: lists Kubernetes Workflow listing request.
   - `plan_argo_workflows_logs`: lists Kubernetes Workflow retrieval and pod log retrieval requests.
   - `plan_argo_workflows_submit`: lists Kubernetes Workflow submission request.

2. **Command Interception & Echo Deletion**:
   - In each command callback, when `dry_run` or `is_dry_run()` is active, invoke the corresponding plan builder, render the plan via `render_request_plan(...)` (or output structured JSON with real result type when `--json` or `--format json` is active), and return early before invoking network calls or cluster mutations.
   - Delete obsolete `@dry_run_command` decorators from these commands.
   - Annotate all 20 external-request commands with `@dry_run_class("request-plan")`.
   - Annotate `argo cd gitops drift` and `argo gitops drift` with `@dry_run_class("no-external-request")`.

3. **Gaps Ratchet**:
   - Remove the 22 commands from `tests/fixtures/dry_run_gaps.json`.

## Rejected Alternatives
1. **Mock execution of network requests during dry run**:
   *Evidence*: Violates owner rule #412 and AGENTS.md Rule 2. A dry run makes zero external requests and prints the requests that a real run will make.
2. **Retaining echo-only preview decorators (`@dry_run_command`)**:
   *Evidence*: Echo output only repeats CLI parameters without describing the HTTP or Kubernetes API requests that the command will make.
