# Proposal: #6752

## Why

The manifest change in #6341 points new volumes at `local-path-retain`.
The live cluster has 8 bound PersistentVolumes with reclaim policy `Delete` and StatefulSets that name `local-path`.
Kubernetes refuses an in-place change of a bound claim `storageClassName` and of StatefulSet `volumeClaimTemplates`.
A person must execute the migration in a maintenance window after the manifest sync.
The repository needs an ordered, documented runbook in `k8s/README.md`.

## What Changes

- Add a `Local-Path Retain Migration` section to `k8s/README.md`.
- Detail the ordered migration: patch bound PersistentVolumes to `Retain` before deleting live StatefulSets with `--cascade=orphan`.
- Provide the exact `kubectl patch pv` command and the `kubectl get pv` listing command that filters on `Delete`.
- Provide the `kubectl delete statefulset --cascade=orphan` command and verification commands waiting for Ready status.
- Add test `tests/k8s/test_k8s_retain_migration_docs.py` to assert the section and exact commands.

## Capabilities

### Modified
- `k8s-docs`: Added the `Local-Path Retain Migration` runbook to `k8s/README.md`.

## Impact

Engineers have a clear, tested runbook to migrate bound volumes to `Retain` and recreate live StatefulSets without data loss.

## Feasibility

Confirmed against the real system: Kubernetes refuses modifying `volumeClaimTemplates` on live StatefulSets.
Using `kubectl patch pv` to set `Retain` and `kubectl delete statefulset --cascade=orphan` safely preserves underlying data and pods.

## Existing Tool Considered

`kubectl` is the standard tool to patch volume reclaim policies and perform orphan StatefulSet deletions.
No custom code is built for a one-time migration.
