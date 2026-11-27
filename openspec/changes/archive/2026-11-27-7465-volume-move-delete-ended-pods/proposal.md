# Proposal

## Why

`devops k8s volume move` leaves the pods that have ended out of its plan (#7431), but the claim protection of the cluster still counts such a pod as a user of the claim. So the delete of the old claim, the point of no return, waited until its timeout, and the move stopped stranded. On 2026-11-27 the move of `gitea/gitea-shared-storage` stopped in this way on an ended pod of an old ReplicaSet (dan-petty/homelab#472), and the delete of `devops/renovate-cache` waited for three ended Renovate pods (#7465).

## What Changes

- Right before the delete of the old claim, the run reads the pods that name the claim and have ended (`_ended_claim_pods`), and deletes them. They hold no data, so the run adds no undo for them.
- The step text and the dry run name the delete of the ended pods.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: a volume move deletes the ended pods of the claim before the old claim.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Move a volume to another node, step 6)

## Feasibility

- Read on the homelab, 2026-11-27: `kubectl describe pvc` listed the ended pods under "Used By", and the claims went away when those pods were deleted.
- A live move of a test claim with an ended pod that names it: the run deleted the pod at step 9, and the move ended in 56 s.

## Existing Tool Considered

The move tool exists; the change adds one read and one delete before the delete of the claim: about 6k tokens and 30 minutes.

## Dependencies

None.
