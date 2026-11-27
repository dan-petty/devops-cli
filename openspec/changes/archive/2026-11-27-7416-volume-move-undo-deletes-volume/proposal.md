# Proposal

## Why

When `devops k8s volume move` fails before the point of no return, its undo deleted the temporary claim `<claim>-move` and left its volume when the class has the reclaim policy `Retain`. The class `longhorn` of the homelab has `Retain`, so each undone move to it (#7382) left a `Released` Longhorn volume with a partial copy, two replicas on the storage nodes, until a person deleted it (#7416).

## What Changes

- The undo of `<claim>-move` reads the volume of the claim when it runs, sets its reclaim policy to `Delete`, and then deletes the claim. A class with `Immediate` binding, such as `longhorn`, has a volume before the destination pod starts, so the undo reads it at that time and not from the run.
- Add `CONST_K8S_RECLAIM_DELETE` and the undo text `volume_move_undo_discard`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: the undo of a volume move deletes the volume that the move made.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Move a volume to another node)

## Feasibility

- Read on the homelab, 2026-11-27: after an undone move to `longhorn`, the volume of `data-move` stayed `Released` with the class `longhorn` and the policy `Retain`; a patch to `Delete` made Longhorn delete it and its replicas.
- StorageClass `longhorn` has `volumeBindingMode: Immediate` and `reclaimPolicy: Retain`.

## Existing Tool Considered

The undo exists. The change adds one read and one patch to the undo of the temporary claim: about 5k tokens and 30 minutes.

## Dependencies

None.
