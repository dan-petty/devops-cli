# Tasks

## 1. Copy from pod to pod

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/k8s/volume_move_measure.py`, `tests/k8s/test_k8s_volume_move.py`, `tests/k8s/test_k8s_volume_measure.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/k8s/test_k8s_volume_move.py`, `tests/k8s/test_k8s_volume_measure.py`.

- [x] 1.1 Write the tests of the copy script, the NetworkPolicy, its order in the run, the undo and the dry run, and of the leftover, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py tests/k8s/test_k8s_volume_measure.py`
- [x] 1.2 Replace the copy script, and add the NetworkPolicy to the run, the undo, the leftovers and the dry run.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py tests/k8s/test_k8s_volume_measure.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Update `k8s/README.md` (Move a volume to another node) and the generated command reference.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Done 2026-11-27: a live move on the homelab of a claim of 737,979,517 bytes from `local-path` on one node to `local-path` on another, in a namespace with a NetworkPolicy that allows no ingress and no egress. The first copy passed, the two sides were equal, and the move took 22 s.
