# Design

## Decisions

### StorageClass for new stateful volumes
Use `local-path-retain` for new stateful volumes. Homelab provides this class backed by the existing `rancher.io/local-path` provisioner with `reclaimPolicy: Retain`.

### Argo CD sync safety on bound claims
Use `spec.ignoreDifferences` for the storage class field (`/spec/storageClassName` on PVCs and `/spec/volumeClaimTemplates/0/spec/storageClassName` on StatefulSets) and set `RespectIgnoreDifferences=true` in `spec.syncPolicy.syncOptions`. The Kubernetes API server rejects mutations to `storageClassName` on existing bound claims. Ignoring the difference in Argo CD prevents sync failures while applying the new class for new volumes.

### Scope of affected Argo CD Applications
The seven applications managing workloads with bound claims or claim templates are `devops`, `gitea`, `mattermost`, `grafana`, `prometheus`, `pyroscope`, and `tempo`.

### Existing bound volumes migration
Document the `kubectl patch pv <name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'` procedure in `k8s/README.md`. Live patching of bound volumes and StatefulSet recreation are deferred to #6752.

## Rejected alternatives

### Change StorageClass to fast-nvme
Rejected: `fast-nvme` implies dedicated NVMe media, but uses the same underlying directories.

### Keep local-path
Rejected: `local-path` uses `reclaimPolicy: Delete`, risking data loss on claim deletion.

### Recreate each claim in this change
Rejected: Recreating live claims causes downtime and requires manual data migration.

### Use ServerSideApply=true alone
Rejected: Server-side apply does not bypass immutable field validations on bound PersistentVolumeClaims.
