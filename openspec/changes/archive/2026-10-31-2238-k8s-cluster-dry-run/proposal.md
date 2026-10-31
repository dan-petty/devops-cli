# Proposal: Dry-Run Classification for Kubernetes Cluster Commands

## Why
Issue #2238 is part of #886. The owner dry-run rule states that a dry run makes no external requests and returns the requests that the real run will make. Fourteen Kubernetes cluster read and access commands in `src/devops_cli/commands/k8s/` do not follow this rule:
- Eleven commands make external requests to Kubernetes APIs, kubectl, minikube, or network endpoints without a request plan.
- One command (`port-forward-stop`) modifies local process state without a dry-run preview.
- Two commands (`gpu-matrix` and `port-forward-status`) execute purely local operations but lack the `no-external-request` classification.

This change classifies all fourteen commands, provides request plans or local previews, and removes echo-only previews.

## What Changes
- Add the `request-plan` classification and request plan output to:
  `k8s audit`, `k8s contexts`, `k8s logs`, `k8s pods`, `k8s port-forward`, `k8s rbac-audit`, `k8s security-stream`, `k8s service-url`, `k8s status`, `k8s stream-logs`, `k8s switch-context`.
- Add the `no-external-request` classification to mark-only commands:
  `k8s gpu-matrix`, `k8s port-forward-status`.
- Add `--dry-run` and the `no-external-request` classification to `k8s port-forward-stop` with a preview that terminates no daemons.
- Remove obsolete echo-only previews (`render_dry_run_result`) from the modified commands with no backwards compatibility shim.
- Remove all fourteen commands from `tests/fixtures/dry_run_gaps.json`.
- The change fits in one pull request.

## Feasibility
- Verified the fourteen commands in `src/devops_cli/commands/k8s/`:
  - `gpu_matrix_cmd` in `src/devops_cli/commands/k8s/gpu_matrix.py` reads local constants only.
  - `port_forward_status` in `src/devops_cli/commands/k8s/networking.py` reads local file state only.
  - `port_forward_stop` in `src/devops_cli/commands/k8s/networking.py` terminates processes.
  - `k8s_audit` and `rbac_audit` in `src/devops_cli/commands/k8s/security_audit.py` execute Popeye and kubectl.
  - `contexts`, `status`, `switch_context`, and `logs` in `src/devops_cli/commands/k8s/cluster_context.py` execute client and kubectl calls.
  - `pods_cmd`, `stream_logs_cmd`, and `security_stream_cmd` in `src/devops_cli/commands/k8s/diagnostics.py` execute client and log streaming calls.
  - `service_url` in `src/devops_cli/commands/k8s/networking.py` executes HTTP proxy requests when `--fetch` is active.
- All fourteen commands exist in `tests/fixtures/dry_run_gaps.json`.

## Existing Tool Considered
The change uses existing internal abstractions:
`devops_cli.dry_run.requests.PlannedRequest`, `render_request_plan`, and `@dry_run_class`.
No third-party library is needed. Deletes 9 uses of `render_dry_run_result` across the Kubernetes command modules.
