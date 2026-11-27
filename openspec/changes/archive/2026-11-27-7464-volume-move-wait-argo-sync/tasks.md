# Tasks

## 1. Wait for the running syncs

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the tests of a running sync, of no running sync and of a sync that does not end, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Wait for the running syncs after the pause and before the delete of the copy pods, and list the waits in the dry run.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Name the wait in `k8s/README.md` (Move a volume to another node, step 1).
  - Verification: `$ uv run devops ci docs`
