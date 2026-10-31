# Proposal: Dry-Run Classification for Kubernetes Manifest, Stack, and Kustomize Commands

## Why
Issue #2239 is part of #886. The owner dry-run rule states that a dry run makes no external requests and returns the requests that the real run will make. Eighteen Kubernetes manifest, stack, and kustomize commands in `src/devops_cli/commands/k8s/` and `src/devops_cli/commands/kustomize.py` do not follow this rule:
- Sixteen commands make external requests to Kubernetes APIs, kubectl, helm, minikube, or network endpoints without a request plan.
- Two commands (`lint` and `validate-policy`) execute local manifest linters/evaluators but lack the `no-external-request` classification.

This change classifies all eighteen commands, provides request plans or local execution markers, and removes echo-only previews.

## What Changes
- Add the `request-plan` classification and request plan output to:
  `k8s apply`, `k8s bootstrap`, `k8s bootstrap-openwebui`, `k8s chaos`, `k8s check-deprecated`, `k8s configure-urls`, `k8s create-tls-secret`, `k8s diff-helm`, `k8s enable-tls`, `k8s render`, `k8s sync-secrets`, `k8s teardown-stack`, `k8s validate`, `kustomize apply`, `kustomize build`, and `kustomize diff`.
- Add `--dry-run` to commands that previously lacked the option: `k8s render`, `kustomize build`, `kustomize diff`.
- Add the `no-external-request` classification to mark-only commands: `k8s lint` and `k8s validate-policy`.
- Remove obsolete echo-only previews (`render_dry_run_result` and `@dry_run_command`) from the modified commands with no backwards compatibility shim.
- Remove all eighteen commands from `tests/fixtures/dry_run_gaps.json`.
- The change fits in one pull request.

## Feasibility
- Verified the eighteen commands in `src/devops_cli/commands/k8s/` and `src/devops_cli/commands/kustomize.py`:
  - `apply` in `src/devops_cli/commands/k8s/cluster_context.py` delegates to `kubectl apply`.
  - `render` in `src/devops_cli/commands/k8s/cluster_context.py` builds kustomizations with `kubectl kustomize`.
  - `bootstrap` in `src/devops_cli/commands/k8s/bootstrap.py` invokes minikube, `deploy_stack`, and `configure_urls`.
  - `bootstrap_openwebui`, `sync_secrets`, and `teardown_stack` in `src/devops_cli/commands/k8s/stack_lifecycle.py` execute kubectl and helm operations.
  - `chaos_cmd` and `diff_helm_cmd` in `src/devops_cli/commands/k8s/diagnostics.py` execute kubectl and helm diff.
  - `configure_urls` in `src/devops_cli/commands/k8s/networking.py` executes kubectl ingress queries.
  - `create_tls_secret` and `enable_tls_stack` in `src/devops_cli/commands/k8s/tls_management.py` execute kubectl namespace checks and secret creation.
  - `k8s_lint`, `k8s_check_deprecated`, `k8s_validate`, and `validate_policy_cmd` in `src/devops_cli/commands/k8s/security_audit.py` execute local scanners and tools.
  - `build`, `diff`, and `apply` in `src/devops_cli/commands/kustomize.py` delegate to kustomize and kubectl diff/apply.
- All eighteen commands are listed in `tests/fixtures/dry_run_gaps.json`.

## Existing Tool Considered
The change uses existing internal abstractions:
`devops_cli.dry_run.requests.PlannedRequest`, `render_request_plan`, and `@dry_run_class`.
No third-party library is needed. Deletes echo-only previews (`render_dry_run_result` and `@dry_run_command`) across the affected Kubernetes and kustomize command modules.
