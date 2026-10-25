# Design

## Context

See proposal.md for motivation and problem background. DevOps CLI deploys Helm charts across multiple stacks (`infra`, `llm`, `gitea`, `logging`). Previously, conflict resolution inspected stderr strings and modified resource metadata with `kubectl`. Helm 3.17 introduced `--take-ownership` to handle existing resources natively, and `helm status -o json` provides structured machine-readable state inspection.

## Goals / Non-Goals

**Goals:**
- Eliminate regex parsing of human stderr strings during Helm operations.
- Recover pending release states (`pending-install`, `pending-upgrade`, `pending-rollback`) via Helm native lifecycle commands (`helm uninstall`, `helm rollback`) before attempting `helm upgrade --install`.
- Use `--take-ownership` on all `helm upgrade --install` commands.
- Verify Helm version >= 3.17 once prior to release deployments.
- Eliminate obsolete retry loops, constants, and manual `kubectl` labeling/annotation loops.

**Non-Goals:**
- Supporting Helm versions prior to 3.17: pre-1.0 alpha software maintains no backward compatibility or shims.
- Changing chart values or manifests.

## Decisions

### Decision: Check Helm version once with standard `packaging.version.Version`
- **Choice**: Call `helm version --template {{.Version}}` once in `deploy_stack` when Helm releases are present, parse the version string with `packaging.version.Version`, and fail with `KubernetesDeployError` if version < 3.17.
- **Rationale**: CONTRIBUTING.md mandates using standard parsers (`packaging`) for open domains like software versions. Checking once avoids spawning redundant `helm version` subprocesses for each release.
- **Alternative Considered**: Parsing version strings manually with regex or splitting on dots. Rejected because manual version splitting does not handle pre-releases or complex version schemas correctly.
- **Alternative Considered**: Checking version on every single release installation. Rejected because Helm version does not change between releases during a single CLI command run.

### Decision: Inspect status before upgrade using `helm status -o json`
- **Choice**: Execute `helm status <release> -n <namespace> -o json` prior to `helm upgrade --install`. If the release is not found, continue to upgrade. If status is `pending-install`, execute `helm uninstall <release> -n <namespace>`. If status is `pending-upgrade` or `pending-rollback`, execute `helm rollback <release> -n <namespace>`.
- **Rationale**: `helm status -o json` provides a stable schema (`info.status`) regardless of Helm's human-readable formatting or terminal localization. Rolling back restores the prior working revision rather than deleting Secret state.
- **Alternative Considered**: Deleting Helm Secret locks with `kubectl delete secret`. Rejected because it assumes the Secret storage driver and leaves Helm release history in an inconsistent state.
- **Alternative Considered**: Reacting after failure by inspecting stderr for error messages. Rejected because human error strings change across Helm releases (such as Helm 3 vs Helm 4).

### Decision: Delegate resource adoption entirely to Helm `--take-ownership`
- **Choice**: Pass `--take-ownership` on all `helm upgrade --install` commands and delete `_adopt_helm_resource_if_conflict` and `CONST_HELM_OWNERSHIP_CONFLICT_RE`.
- **Rationale**: Helm 3.17+ natively adopts existing resources that match the chart. Removing the kubectl label/annotate loop eliminates round-trips and fragile regex matching.
- **Alternative Considered**: Keeping a fallback kubectl adoption loop if `--take-ownership` fails. Rejected because pre-1.0 alpha rules mandate zero legacy shims or zombie code.

## Risks / Trade-offs

- [Risk] Helm 3.16 or older environments fail deployment. → Mitigation: Clear error message explicitly naming the installed version and the required version (3.17 or later).
- [Risk] Rollback on a release with no prior revision. → Mitigation: `pending-install` is uninstalled instead of rolled back; `pending-upgrade` and `pending-rollback` only occur when a prior revision exists.
