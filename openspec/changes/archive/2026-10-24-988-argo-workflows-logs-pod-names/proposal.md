# Proposal

## Why

Issue #988: The `devops argo workflows logs <workflow>` command fails to read logs from real Argo Workflows installations. The command returns two errors before reading any log:
1. Pod names are derived incorrectly as raw node identifiers instead of following Argo Workflows pod naming conventions (`POD_NAMES=v1` or `v2`), causing 404 Not Found errors.
2. The log stream call specifies no container name, causing the Kubernetes API server to return HTTP 400 Bad Request because workflow pods contain both `main` and `wait` containers.

## What Changes

- Add deterministic pod name resolution to `ArgoCRDService.workflow_pod_names` supporting both `v1` (node identifier) and `v2` (`<workflow>-<templateName>-<hash>`) formats.
- Compute the v2 hash using standard 32-bit FNV-1a on the node name, matching upstream Argo Workflows controller logic.
- Exclude workflow nodes that were never created, including nodes with skipped or omitted phases.
- Add `--container` (`-c`) option to `devops argo workflows logs`, defaulting to `main`.
- Add automatic fallback from `v2` pod names to `v1` pod names if the initial log stream fails with a 404 Not Found error.
- Update `ArgoCommandHelp` and command documentation.

This change alters observable CLI command options, arguments, and log streaming behavior, so it carries a spec delta (`argo-workflow-logs`).

This change fits in one pull request.

## Capabilities

### New Capabilities

- `argo-workflow-logs`: Native pod name resolution and container selection for streaming Argo Workflows execution logs.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/argo/crd.py`: Update `workflow_pod_names` to derive pod names with FNV-32a hashing, support `v1` and `v2`, and omit skipped nodes.
- `src/devops_cli/commands/argo.py`: Add `--container` option defaulting to `main`, pass container to `read_pod_logs`, and handle 404 fallback from `v2` to `v1`.
- `src/devops_cli/lang/en/help.py`: Add help text for `--container` in `ArgoCommandHelp`.
- `docs/commands/argo.md`: Regenerated via `devops docs generate --sync-readme`.
- Unit tests in `tests/test_argo.py` and `tests/test_argo_crd.py`.

## Feasibility

I confirmed the premise against the real system:

- Checked upstream Argo Workflows controller source code (`workflow/util/pod_name.go`) and UI implementation (`ui/src/shared/pod-name.ts`). They generate v2 pod names as `<workflow>-<templateName>-<hash>` where `<hash>` is the decimal FNV-32a hash of the node name, while single-container entrypoint templates use the workflow name directly.
- Submitted live workflows to the local homelab Kubernetes cluster running Argo Workflows controller v4.1.5 (`argo-workflows-workflow-controller-9fc99bcfb-nndv8`).
- A single-step container workflow generated pod `test-hello-w96hw`, matching `workflowName`.
- A multi-step workflow generated pod `test-steps-8cgzv-echo-step-609221141`. Node name `test-steps-8cgzv[0].step1` hashed to `609221141` under FNV-32a, matching the actual pod name.
- A workflow with conditional execution confirmed that nodes with phase `Skipped` or `Omitted` create no Kubernetes pods.
- Checked Kubernetes API server behavior: calling `read_namespaced_pod_log` without a container on an Argo pod returns HTTP 400 with message "a container name must be specified".

## Existing Tool Considered

We considered executing the external `argo` CLI tool (`argo logs <workflow>`). We rejected this approach because `devops` operates natively against the Kubernetes API through `CoreV1Api` and `CustomObjectsApi`. Invoking the external CLI introduces an external binary dependency that is absent in minimal container environments. Upstream Argo pod naming conventions are open, deterministic, and easily derived directly from the custom resource status.

Deleted internal code: Replaced the naive node ID list comprehension in `src/devops_cli/argo/crd.py:workflow_pod_names`.
