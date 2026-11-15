# Proposal

## Why

`devops k8s volume move` gave the source copy pod only the tolerations of the workload pod. A workload has no toleration for `node.kubernetes.io/unschedulable`, so a move off a cordoned node passed the plan and left its copy pod Pending. A cordon is the usual reason to move a claim (#5305).

## What Changes

- Add `CONST_K8S_UNSCHEDULABLE_TAINT` and give the source copy pod a toleration of that taint with `operator: Exists` and `effect: NoSchedule`.
- Keep the tolerations of the workload pod.
- Update `test_the_copy_pods_mount_each_claim_on_its_own_node` with the new toleration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: the source copy pod tolerates a cordon.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/k8s/volume_move.py:427` copies only `plan.source_tolerations`.
- A pod that tolerates `node.kubernetes.io/unschedulable` with `effect: NoSchedule` schedules on a cordoned node.
- `uv run pytest tests/k8s/test_k8s_volume_move.py` passes with 42 tests.

## Existing Tool Considered

The move tool exists. The change adds one toleration: about 200 tokens to build and 10 a quarter to keep.

## Dependencies

None.
