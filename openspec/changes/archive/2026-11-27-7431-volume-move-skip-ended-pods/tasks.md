# Tasks

## 1. Leave out the ended pods

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the test of an ended pod of the claim, and watch it fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Leave out the pods in phase `Succeeded` or `Failed` in `_claim_pods`.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Name the left-out pods in `k8s/README.md` (Move a volume to another node, step 3).
  - Verification: `$ uv run devops ci docs`
