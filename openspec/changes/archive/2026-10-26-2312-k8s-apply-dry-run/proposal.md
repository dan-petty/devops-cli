# Proposal

## Why

Issue #2312: `devops k8s apply` declares `--dry-run`, but the command does not set the dry-run state, and it reads only `is_dry_run()`. With only the `--dry-run` flag, `is_dry_run()` is `False`, so the command runs `runtime._run_cmd`, which starts `kubectl apply -f <path> --dry-run=client` against the Kubernetes cluster. Under #412 and #986, contacting a remote cluster in a dry run is an external communication.

## What Changes

- `apply` checks `dry_run or is_dry_run()` and renders the preview with `render_dry_run_result` before the subprocess runner.
- `_apply_template`, the `--template` and `--domain` path of `k8s apply`, checks `dry_run or is_dry_run()` the same way.
- In a dry run the command renders the preview and starts zero child processes.
- The change adds the capability `k8s-apply-dry-run`: a command's dry-run behavior is observable.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-apply-dry-run`: the dry-run behavior of `devops k8s apply`.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/k8s/cluster_context.py`, `tests/test_k8s_context.py`.

## Feasibility

- Command output: the issue cites `cluster_context.py` lines 182 to 231. At the base commit the dry-run preview is gated on `is_dry_run()` alone, and the command reaches `runtime._run_cmd` when only `--dry-run` is set. The new test fails on it.

## Existing Tool Considered

No outside tool applies. The change reuses `render_dry_run_result` and gates the existing preview on the command's own flag.
