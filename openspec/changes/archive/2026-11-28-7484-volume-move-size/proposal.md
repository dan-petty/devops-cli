# Proposal

## Why

`devops k8s volume move` made `<claim>-move` with the size of the old claim. A `local-path` volume does not limit its data to the size of its claim, but `longhorn` does. On 2026-11-27 the move of `devops/roadmap-service-home` failed with `No space left on device`: it held 3,528,025,691 bytes in a claim of 1Gi. The size in git cannot help, because the move takes the size of the live claim, and a bound `local-path` claim cannot grow (#7484).

## What Changes

- Add `--size QUANTITY` to `devops k8s volume move`. `<claim>-move` and the claim made again request that size; without it, they keep the size of the old claim.
- The plan refuses a size that `kubernetes.utils.quantity.parse_quantity` cannot read, and a size under the size of the old claim.
- `--plan` prints `Size: <old> now, <new> after the move.`; the dry run shows the size in both claim manifests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: a volume move can make the new claim larger.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Change the class of a volume), `docs/commands/k8s.md`

## Feasibility

- A live move on the homelab, 2026-11-28: a `local-path` claim of 1Gi held 1,289,748,480 bytes; with `--storage-class longhorn --size 2Gi` the move ended in 39 s with equal digests, and the claim is `longhorn`, 2Gi, Bound.

## Existing Tool Considered

The Kubernetes Python client parses the quantity (`kubernetes.utils.quantity.parse_quantity`), as `devops_cli.infra.status` does. The change adds one option beside `--access-mode`: about 12k tokens and 45 minutes.

## Dependencies

None.
