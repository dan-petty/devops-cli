# Proposal

## Why

DevOps CLI recovered stuck Helm releases and adopted conflicting resources by parsing human error text in stderr with regular expressions and manipulating Secret locks and annotations with `kubectl` (#1438). This approach was fragile against Helm wording changes, assumed the Secret storage driver, and discarded revisions instead of rolling back.

This change fits one pull request.

## What Changes

- Verify installed Helm version before deployment and require Helm 3.17 or later; fail with an error naming the installed version when older.
- Inspect Helm release state before `helm upgrade --install` using `helm status -o json`.
- Automatically uninstall releases in `pending-install` state before upgrade.
- Automatically rollback releases in `pending-upgrade` or `pending-rollback` state to their previous revision with `helm rollback <release>` before upgrade.
- Pass `--take-ownership` on all `helm upgrade --install` command executions so Helm adopts existing resources natively.
- Delete `_recover_stuck_helm_release_if_pending`, `_adopt_helm_resource_if_conflict`, `_run_helm_with_adoption_retries`, and regular expression `CONST_HELM_OWNERSHIP_CONFLICT_RE`.
- Remove `DEFAULT_HELM_RECOVERY_MAX_RETRIES` setting and delete the `kubectl annotate` / `kubectl label` loop.
- Reword import failure messages in `src/devops_cli/ai/library/introspector.py` and `src/devops_cli/exceptions/ai.py` so obsolete strings do not match in `src`.

## Capabilities

### New Capabilities
- `k8s-helm-deploy`: Helm release deployment, version verification, state recovery, and ownership adoption for Kubernetes stacks.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/k8s/stack_lifecycle.py`: Helm deployment command construction, single-point version check, and JSON status recovery.
- `src/devops_cli/commands/k8s/__init__.py`: Clean up exports of removed helpers.
- `src/devops_cli/config/constants.py`: Remove `CONST_HELM_OWNERSHIP_CONFLICT_RE` and add `CONST_HELM_MIN_VERSION`.
- `src/devops_cli/config/defaults.py`: Remove `DEFAULT_HELM_RECOVERY_MAX_RETRIES`.
- `tests/test_k8s.py`: Remove obsolete stderr matching tests and add tests for status inspection, rollback, uninstall, `--take-ownership`, and version checking.

## Feasibility

The premise was verified against the real system:
- `helm version` reports `version.BuildInfo{Version:"v4.3.0", ...}` in the environment.
- `helm upgrade --help` confirms the `--take-ownership` flag is available: "if set, upgrade will ignore the check for helm annotations and take ownership of the existing resources".
- `helm status --help` confirms `-o json` output and release states: `pending-install`, `pending-upgrade`, `pending-rollback`.
- `helm rollback --help` confirms rollback to the previous revision via `helm rollback <RELEASE> [REVISION] [flags]`.
- Upstream Helm introduced `--take-ownership` in Helm 3.17.0.

## Existing Tool Considered

Helm CLI (3.17+) provides native ownership adoption through `--take-ownership` and release recovery commands (`helm rollback`, `helm uninstall`). DevOps CLI previously maintained a custom regular expression (`CONST_HELM_OWNERSHIP_CONFLICT_RE`) and custom `kubectl annotate` and `kubectl label` adoption routines. Adopting Helm's native `--take-ownership` replaces this custom code. Replaced internal code includes `_adopt_helm_resource_if_conflict`, `_recover_stuck_helm_release_if_pending`, `_run_helm_with_adoption_retries`, `CONST_HELM_OWNERSHIP_CONFLICT_RE`, and `DEFAULT_HELM_RECOVERY_MAX_RETRIES`.
