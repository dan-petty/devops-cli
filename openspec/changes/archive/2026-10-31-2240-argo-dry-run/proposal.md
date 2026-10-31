# Proposal: Dry-Run Classification for Argo Commands

## Why
Issue #2240 is part of #886. The owner dry-run rule states that a dry run makes no external request and returns the requests that the real run will make. Twenty-two Argo commands in `src/devops_cli/commands/argo.py` do not follow this rule:
- Twenty commands make external requests to Argo CD REST APIs, Prometheus, or the Kubernetes API without a request plan.
- Two commands (`argo cd gitops drift` and `argo gitops drift`) calculate local file status against git and make no external request, but lack the `no-external-request` classification.

This change classifies all twenty-two commands, adds request plans, adds missing `--dry-run` options, and removes echo-only previews.

## What Changes
- Add the `request-plan` classification and request plan output to:
  `argo cd apps bootstrap-gitops`, `argo cd apps list`, `argo cd apps status`, `argo cd apps sync`, `argo cd fleet sync`, `argo cd gitops sync`, `argo cd gitops watch`, `argo fleet sync`, `argo gitops sync`, `argo gitops watch`, `argo rollouts abort`, `argo rollouts analyze`, `argo rollouts list`, `argo rollouts promote`, `argo rollouts restart`, `argo rollouts status`, `argo sync`, `argo workflows list`, `argo workflows logs`, and `argo workflows submit`.
- Add `--dry-run` to commands that previously lacked the option:
  `argo cd apps sync`, `argo rollouts list`, `argo rollouts status`, `argo sync`, `argo workflows list`, `argo workflows logs`, and `argo workflows submit`.
- Add the `no-external-request` classification to mark-only commands:
  `argo cd gitops drift` and `argo gitops drift`.
- Remove obsolete echo-only previews (`@dry_run_command`) from the modified commands with no backwards compatibility shim.
- List the token request (`POST /api/v1/session`) before Argo CD API requests in dry-run plans.
- Return real result types marked as dry runs when `--format json` or `--json` is supplied.
- Remove all twenty-two commands from `tests/fixtures/dry_run_gaps.json`.
- The change fits in one pull request.

## Feasibility
- Verified the twenty-two commands in `src/devops_cli/commands/argo.py`:
  - `cd_apps_bootstrap_gitops` applies an Application manifest to Kubernetes.
  - `cd_apps_list`, `cd_apps_status`, and `cd_apps_sync` send HTTP requests to Argo CD REST API.
  - `fleet_sync` sends HTTP sync requests to target clusters.
  - `gitops_drift` inspects local files with git only.
  - `gitops_watch` and `gitops_sync` trigger sync requests to Argo CD API or webhook.
  - `rollouts_abort`, `rollouts_analyze`, `rollouts_promote`, and `rollouts_restart` patch Rollout CRDs in Kubernetes.
  - `rollouts_list` and `rollouts_status` read Rollout CRDs from Kubernetes.
  - `argo_sync_cmd` delegates to `cd_apps_sync` or `fleet_sync`.
  - `workflows_list`, `workflows_logs`, and `workflows_submit` interact with Workflow CRDs and Pod logs in Kubernetes.
- All twenty-two commands are listed in `tests/fixtures/dry_run_gaps.json`.

## Existing Tool Considered
The change uses existing internal abstractions:
`devops_cli.dry_run.requests.PlannedRequest`, `render_request_plan`, and `@dry_run_class`.
No third-party library is needed. Deletes echo-only previews (`@dry_run_command`) across the affected Argo command modules.
