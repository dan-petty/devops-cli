# Proposal

## Why

`devops k8s volume move` took each pod that names the claim in its volumes, a pod that has ended included. A node shutdown ends the pods of the node, and the pod garbage collection keeps them up to its threshold. Such a pod of an old ReplicaSet is not deleted by a scale of the Deployment to zero, so the stop step waited for it until its timeout, and the check after the start found it not Running and left the move stranded after the point of no return (#7431).

## What Changes

- `_claim_pods` leaves out a pod whose phase is `Succeeded` or `Failed` (`CONST_K8S_POD_PHASES_ENDED`). The plan, the stop step and the check after the start see only the pods that can hold the volume.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: a volume move leaves out the pods that have ended.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Move a volume to another node, step 3)

## Feasibility

- Read on the homelab, 2026-11-27: `llm/valkey-runs-76d75fb78d-f98jd` has the phase `Succeeded` next to the Running pod of Deployment `valkey-runs`, and the plan of `llm/valkey-runs-data` named both pods. With this change, the plan names only the Running pod.
- Kubernetes: a pod in phase `Succeeded` or `Failed` has stopped its containers and does not block the delete of its claim.

## Existing Tool Considered

The plan exists. The change adds one filter: about 4k tokens and 20 minutes.

## Dependencies

None.
