# Proposal

## Why

Issue #2141 shows that the step in `k8s/README.md` (Alloy Metrics Write-Ahead Log) that moved the `alloy-metrics` write-ahead log onto its volume (#1967) stops half way. After the orphan delete, the new StatefulSet adopts the old pod but cannot replace it, so the claim stays `Pending` and the log stays in the container's own filesystem. The README says that the StatefulSet replaces the pod.

## What Changes

- The step deletes the adopted pod after the orphan delete, so that the StatefulSet makes a pod that mounts the claim.
- The text after the commands says why: Kubernetes does not let a pod's volumes change.
- The change alters a document only, so it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `k8s/README.md`: the Alloy Metrics Write-Ahead Log section.

## Feasibility

Command output, 2026-10-24, on the homelab cluster after #2137 merged and Argo CD synced the `Alloy` resource `k8s-monitoring-alloy-metrics`:

- `kubectl -n monitoring delete statefulset k8s-monitoring-alloy-metrics --cascade=orphan`: the Alloy Operator made the StatefulSet again with the claim template `alloy-wal`, and the StatefulSet adopted pod `k8s-monitoring-alloy-metrics-0`.
- `kubectl -n monitoring get events --field-selector reason=FailedUpdate`: `update Pod k8s-monitoring-alloy-metrics-0 in StatefulSet k8s-monitoring-alloy-metrics failed error: Pod "k8s-monitoring-alloy-metrics-0" is invalid: spec: Forbidden: pod updates may not change fields other than spec.containers[*].image, ...`, with a diff that adds the volume `alloy-wal`. The claim `alloy-wal-k8s-monitoring-alloy-metrics-0` stayed `Pending` (`WaitForFirstConsumer`).
- `kubectl -n monitoring delete pod k8s-monitoring-alloy-metrics-0`: the new pod mounts the claim, the claim is `Bound`, Alloy runs with `--storage.path=/var/lib/alloy`, and the pod and its volume are on a worker node.

## Existing Tool Considered

The step uses `kubectl` only, as the rest of the section does. Nothing is built.
