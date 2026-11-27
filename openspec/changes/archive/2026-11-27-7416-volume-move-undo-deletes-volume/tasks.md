# Tasks

## 1. Delete the volume in the undo

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the tests of the undo after the copy and of a class that binds before the pod, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Read the volume of `<claim>-move` in its undo, set it to `Delete`, then delete the claim.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Name the deleted volume in the undo of `k8s/README.md` (Move a volume to another node).
  - Verification: `$ uv run devops ci docs`
