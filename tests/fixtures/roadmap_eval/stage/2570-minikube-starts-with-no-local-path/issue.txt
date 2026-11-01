## Problem Description

On the devcontainer's minikube, no StorageClass `local-path` exists, so each claim that names it stays `Pending`. `devops devcontainer` starts minikube with `minikube start --driver=docker --cni=calico` (`commands/k8s/cluster_runtime.py`, `_start_minikube`) and enables no storage addon. The default `storage-provisioner` addon of minikube serves only the class `standard`. The class `local-path` comes from the `storage-provisioner-rancher` addon.

Claims that name `local-path`: `k8s/devops/roadmap-service/pvc.yaml`, `k8s/gitea/values.yaml`, `k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/k8s-monitoring-values.yaml` (`alloy-wal`), `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/pyroscope-values.yaml` and `k8s/otel/tempo-values.yaml`.

## Reproduction Steps

1. Start the devcontainer's minikube with `devops devcontainer post-start` (or `bootstrap-k8s`).
2. Run `devops k8s deploy-stack --stack infra`.
3. Run `kubectl get sc` and `kubectl get pvc -A`.

## Expected vs Actual Behavior

- Expected: the class `local-path` exists, and the claims bind.
- Actual: `kubectl get sc` lists only `standard`, and the claims that name `local-path` stay `Pending`.

## Environment Diagnostics

- minikube v1.39.0. `minikube addons list` names `default-storageclass`, `storage-provisioner` and `storage-provisioner-rancher`.
- devops-cli on origin/main 9e73e6d0 (2026-10-28). `k8s/README.md` (Prerequisites) states the step after #1648.

## Logs, Traces, or Terminal Output

Not run on a live minikube: the minikube of this devcontainer was stopped. The evidence is the start command in `cluster_runtime.py` and the addon list of minikube v1.39.0.

## Existing Tool Considered

minikube's own `storage-provisioner-rancher` addon gives the class `local-path` with the rancher provisioner that the homelab runs. The fix is `minikube addons enable storage-provisioner-rancher` after the start, or `--addons=storage-provisioner-rancher` on `minikube start`. Nothing new is built.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=a3eb41f4ca6e58ceeed77b159eb910a3b3151b7a -->
## Proposed design

### Problem statement
The devcontainer's minikube starts without the `local-path` StorageClass. The default `storage-provisioner` addon serves only the class `standard`. Seven PVCs across the infra, gitea, monitoring and otel stacks name `local-path`, so they stay Pending and the services that mount them cannot start. The fix is to enable minikube's `storage-provisioner-rancher` addon on the existing start command.

### Acceptance criteria

### Requirement: local-path StorageClass exists
After `devops devcontainer post-start` completes, the cluster SHALL have a StorageClass named `local-path`.

#### Scenario: StorageClass present after start
- **WHEN** `devops devcontainer post-start` completes successfully
- **THEN** `kubectl get sc local-path` returns the StorageClass with the rancher local-path provisioner

### Requirement: PVCs bind
After `devops k8s deploy-stack --stack infra` completes, every PersistentVolumeClaim that names `local-path` SHALL be in the `Bound` state.

#### Scenario: All local-path PVCs bound
- **WHEN** `devops k8s deploy-stack --stack infra` completes and the PVCs have had time to bind
- **THEN** `kubectl get pvc -A` shows no PVC with `storageClassName: local-path` in the `Pending` state

### Requirement: Start command includes addon
The `_start_minikube` function SHALL pass `--addons=storage-provisioner-rancher` to the `minikube start` command.

#### Scenario: Start command has the addon flag
- **WHEN** The start command is constructed in `_start_minikube`
- **THEN** The command arguments include `--addons=storage-provisioner-rancher`

### Existing Tool Considered
minikube's `storage-provisioner-rancher` addon provides the `local-path` StorageClass with the rancher local-path provisioner, the same provisioner the homelab runs. It lacks nothing. The fix is to add `--addons=storage-provisioner-rancher` to the existing `minikube start` command in `_start_minikube` in `src/devops_cli/commands/k8s/cluster_runtime.py`. No new code is built.

### Key questions
- **Where to enable the addon: on the start command or after start?**: Add `--addons=storage-provisioner-rancher` to the `minikube start` command. This is atomic with the cluster start and follows the pattern of `--cni=calico` added by #990 to the same function. (best practice) [sources: openspec/changes/archive/2026-10-24-990-calico-cni/proposal.md, k8s/README.md]
  - Chosen: --addons=storage-provisioner-rancher on minikube start. Atomic with the start, no race window, follows the --cni=calico pattern from #990 in the same function.
  - Rejected: minikube addons enable storage-provisioner-rancher after start. Two-step, leaves a window where the cluster runs without the class. Adds a second command to maintain.
- **Which provisioner to use: rancher local-path or the default standard class?**: Use the rancher local-path provisioner via `storage-provisioner-rancher`. All seven PVCs name `local-path`, and the homelab runs the same rancher provisioner. Changing every PVC to `standard` would break the homelab and the volume-placement rules. (best practice) [sources: k8s/devops/roadmap-service/pvc.yaml, k8s/gitea/values.yaml, k8s/monitoring/grafana-values.yaml, k8s/monitoring/k8s-monitoring-values.yaml, k8s/monitoring/prometheus-values.yaml, k8s/monitoring/pyroscope-values.yaml, k8s/otel/tempo-values.yaml, k8s/README.md]
  - Chosen: rancher local-path (storage-provisioner-rancher). All PVCs name local-path. The homelab uses the same provisioner. The volume-placement rules and alerts assume local-path semantics.
  - Rejected: default standard class (storage-provisioner). Would require changing every PVC and values file to name standard. Breaks the homelab, which uses local-path. Breaks the volume-placement tests and alerts.
- **Does minikube v1.39.0 ship the storage-provisioner-rancher addon?**: Yes. minikube v1.39.0 lists the addons `default-storageclass`, `storage-provisioner` and `storage-provisioner-rancher` in `minikube addons list`. [sources: openspec/changes/archive/2026-10-29-1648-k8s-readme-homelab/proposal.md, k8s/README.md]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "3e010ca5af5a077203b7069137489d0f1b1c02f7c80f462ab5fe02aa97b088d4", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "8bbf62687d7ec7cce1fee93128079ec395af2b27474f078b628130ed8bff1ba5", "stage.branch": "fix/2570-minikube-starts-with-no-local-path", "stage.file_cap": null, "stage.groups": "[[\"Add storage-provisioner-rancher addon to minikube start\", 3013]]", "stage.needs_split": null, "stage.pr": "2998", "stage.ready": "2998", "stage.sha": "3483e1db733dae9198f252aed107f19aac5d236c"} -->
