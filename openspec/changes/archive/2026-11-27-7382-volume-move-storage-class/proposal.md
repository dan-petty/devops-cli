# Proposal

## Why

`devops k8s volume move NAMESPACE/CLAIM` copies a local-path claim to a new volume on another node, and binds the claim name to that volume. The move claim and the claim made again keep the class of the old claim (`src/devops_cli/k8s/volume_move.py:412`, `:1370`). The homelab moves 16 claims from `local-path` to the replicated class `longhorn` (dan-petty/homelab#399, #390). The class of a claim is immutable, and a claim of `volumeClaimTemplates` must keep its name. So each of these moves needs the steps of the command with a different class (#7382).

## What Changes

- Add `--storage-class CLASS` to `devops k8s volume move`. The move claim `<claim>-move` and the claim made again get CLASS.
- With a class change, the plan picks the target node from the worker nodes that are Ready and schedulable and that can attach a volume of CLASS. When a CSIDriver has the name of the provisioner of CLASS, only the nodes whose CSINode lists that driver can attach it. The node of the old volume can be the target. `--to-node` is optional.
- With a class change, the run makes sure that each pod of the claim runs after the start. It does not require the target node: the scheduler places the pods.
- The plan refuses a class that does not exist, and a `--to-node` that cannot attach the class.
- `--plan` prints the class of the old claim and the target class. `--dry-run` lists the reads of the class, of the CSIDriver and of the CSINodes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: a volume move can change the storage class of the claim.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Move a volume to another node), `docs/commands/k8s.md`

## Feasibility

- Read on `origin/main`, 2026-11-27: `_move_claim_manifest` and `rebound_claim` take the class from the old claim.
- Read on the homelab, 2026-11-27: StorageClass `longhorn` has the provisioner `driver.longhorn.io`; CSIDriver `driver.longhorn.io` exists; the CSINodes of the three storage nodes list it, and the CSINodes of the control-plane node and of the GPU node without a Longhorn disk list no driver. StorageClass `local-path` has the provisioner `rancher.io/local-path`, and no CSIDriver has that name.
- The class of a claim and of its volume must be equal for a bind, so the claim made again with `spec.volumeName` of a `longhorn` volume needs the class `longhorn`.
- The Open WebUI move of dan-petty/homelab#461 did the same steps by hand from `local-path` to `longhorn`.

## Existing Tool Considered

pv-migrate (Apache-2.0) copies data between two claims with rsync, but it does not pause Argo CD, stop the workloads, compare the two sides or bind the old claim name to the new volume. Velero restores a namespace with a class map, but it needs an install and a backup store for each move. The command of this repository has each step except the class. The change costs about 30k tokens and 2 hours to build.

## Dependencies

None.
