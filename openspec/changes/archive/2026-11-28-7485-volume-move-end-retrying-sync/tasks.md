# Tasks

## 1. End a retrying sync

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the tests of an ended operation and of an operation that ends by itself, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 End the running operation of each paused Application and wait for the phase `Failed`.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Describe the end of the operation in `k8s/README.md` (Move a volume to another node, step 1).
  - Verification: `$ uv run devops ci docs`
