# Proposal: #6341

## Why
The stateful workloads of devops-cli ask for StorageClass `local-path`, which has `reclaimPolicy: Delete`. A new volume can lose its data when its claim goes. The cluster now has StorageClass `local-path-retain`, which has `reclaimPolicy: Retain`. The change points each new stateful volume at that class, keeps the Argo CD sync of each bound claim healthy with `ignoreDifferences`, and documents the class and the `kubectl patch pv` step for bound volumes.

## What Changes
- Set `storageClassName: local-path-retain` (or `storageClass: local-path-retain`) across all stateful manifests, Helm values and CloudNativePG Clusters under `k8s/`.
- Add `spec.ignoreDifferences` for `PersistentVolumeClaim` and `StatefulSet` storage class fields and add `RespectIgnoreDifferences=true` in `spec.syncPolicy.syncOptions` across the seven affected Argo CD Applications (`devops`, `gitea`, `mattermost`, `grafana`, `prometheus`, `pyroscope`, `tempo`).
- Add gate checks `check_every_claim_names_the_retain_class` and `check_each_claim_application_ignores_the_storage_class` in `tests/gate/k8s_checks/argocd_apps.py`.
- Add invariant test `tests/invariants/test_k8s_storage_docs.py`.
- Document `local-path-retain` in `k8s/README.md` and `docs/SERVICE_PATTERNS.md`, and document the `kubectl patch pv` command in `k8s/README.md`.
- Introduce `k8s-stateful-storage` specification.

## Capabilities
- `k8s-stateful-storage`: NEW capability for stateful volume storage class standards and Argo CD ignore configuration.

## Impact
- New stateful volumes in the cluster are provisioned with `reclaimPolicy: Retain`.
- Bound claims keep their existing volumes and Argo CD sync stays healthy without attempting immutable storage class changes.

## Feasibility
- Tested against the 11 files (12 occurrences) in `k8s/` and the seven Argo CD applications.

## Existing Tool Considered
- `rancher/local-path-provisioner` (Apache-2.0, maintained) is already in use by the cluster and provides both `local-path` and `local-path-retain`. No new tool is needed.
- Build cost: about 60 lines of manifests/config and test code; about 25k tokens and 25 minutes.
