# Tasks

## 1. Delete the ended pods before the old claim

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/lang/en/messages.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the tests of the run and the dry run with an ended pod of the claim, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Delete the ended pods of the claim right before the delete of the old claim.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Name the delete of the ended pods in `k8s/README.md` (Move a volume to another node, step 6).
  - Verification: `$ uv run devops ci docs`
