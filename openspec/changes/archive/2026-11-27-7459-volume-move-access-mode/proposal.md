# Proposal

## Why

`devops k8s volume move` made `<claim>-move` and the claim made again with the access modes of the old claim. A `local-path` claim that several pods mount holds all of them on one node. On `longhorn`, a `ReadWriteOnce` volume attaches to one node only, so a pod on another node cannot start, and a rolling update can deadlock. The access modes of a bound claim are immutable, and the claim must keep its name. The owner chose `ReadWriteMany` on `longhorn` on 2026-11-27 for `pixelfed-storage` (dan-petty/danielpetty.com#108) and `roadmap-service-home` (dan-petty/homelab#579) (#7459).

## What Changes

- Add `--access-mode MODE` to `devops k8s volume move`, checked against `CONST_K8S_ACCESS_MODES`. `<claim>-move` and the claim made again get `accessModes: [MODE]`; without it, they keep the modes of the old claim.
- `VolumeMovePlan.target_access_modes` is empty when the move keeps the modes; `new_access_modes` gives the modes of the new claims. `rebound_claim` takes the access modes.
- `--plan` prints `Access modes: <old> now, <new> after the move.`; `--dry-run` shows the new modes in both claim manifests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: a volume move can change the access mode of the claim.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Change the class of a volume), `docs/commands/k8s.md`

## Feasibility

- Read on the homelab, 2026-11-27: a `longhorn` claim with `ReadWriteMany` mounted in two pods on two storage nodes through the Longhorn share manager, and owners set as root (`999:1000`, `33:33`) showed in the other pod.
- The live move of this change: a `local-path` claim of two Deployments moved to `longhorn` with `ReadWriteMany`; the two pods then ran on two storage nodes, and the `sha256sum` of all files and the owners were the same.

## Existing Tool Considered

The move tool exists; the change adds one option beside `--storage-class`: about 15k tokens and 1 hour.

## Dependencies

None.
