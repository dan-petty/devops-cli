# Design: Dry-Run Classification for Kubernetes Manifest, Stack, and Kustomize Commands

## Context
Commands in `k8s` and `kustomize` handle manifest preparation, deployment, stack teardown, secret synchronization, and validation. In a dry run, any command that communicates with an external cluster or subprocess must return a plan of its intended actions rather than executing requests or returning simulated mock responses. Commands that perform purely local work without network or cluster interaction are classified as `no-external-request`.

## Technical Strategy
1. **Planned Request Construction**:
   Create `src/devops_cli/k8s/manifest_plans.py` containing dedicated plan builders for the 16 external-request commands:
   - `plan_k8s_apply`: builds `kubectl apply` invocation.
   - `plan_k8s_render`: builds `kubectl kustomize` invocation.
   - `plan_k8s_bootstrap`: builds minikube start/context, stack deployment, and url configuration invocations.
   - `plan_k8s_bootstrap_openwebui`: builds pod discovery and exec requests.
   - `plan_k8s_chaos`: builds pod query, pod deletion, and rollout status monitoring requests.
   - `plan_k8s_check_deprecated`: builds Pluto deprecation detection command.
   - `plan_k8s_configure_urls`: builds ingress discovery query.
   - `plan_k8s_create_tls_secret`: builds namespace existence check and TLS secret creation commands.
   - `plan_k8s_diff_helm`: builds `helm diff` command.
   - `plan_k8s_enable_tls`: builds namespace checks and TLS secret creations across selected stack namespaces.
   - `plan_k8s_sync_secrets`: builds secret fetch and token generation requests.
   - `plan_k8s_teardown_stack`: builds delete commands for manifests, custom resources, and Helm uninstalls.
   - `plan_k8s_validate`: builds Kubeconform schema validation invocation.
   - `plan_kustomize_apply`: builds `kubectl apply -k` invocation.
   - `plan_kustomize_build`: builds `kustomize build` invocation.
   - `plan_kustomize_diff`: builds `kubectl diff -k` invocation.

2. **Command Interception & Echo Deletion**:
   - In each command callback, when `dry_run` or `is_dry_run()` is active, invoke the corresponding plan builder, render the plan via `render_request_plan(...)`, and return early before invoking subprocesses, network requests, or OS Keyring modifications.
   - Delete obsolete `render_dry_run_result(...)` and `@dry_run_command` decorators from these commands.
   - Annotate all 16 commands with `@dry_run_class("request-plan")`.
   - Annotate `k8s lint` and `k8s validate-policy` with `@dry_run_class("no-external-request")`.

3. **Gaps Ratchet**:
   - Remove the 18 commands from `tests/fixtures/dry_run_gaps.json`.

## Rejected Alternatives
1. **Executing client-side `--dry-run=client` against a real cluster**:
   *Evidence*: Violates owner rule #412 and AGENTS.md Rule 2/Rule 10. A dry run must run completely offline without cluster credentials, network egress, or active daemon sockets.
2. **Keeping simulated echo output (`render_dry_run_result`)**:
   *Evidence*: Echo output merely repeats user arguments without describing the actual executable calls (kubectl, helm, pluto) that will be performed.
