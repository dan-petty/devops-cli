# Tasks

## 1. Leave lost+found out of the compare

Kind: behavior.

Reads: `src/devops_cli/config/constants.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/config/constants.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the test that each `find` of the digest script prunes `./lost+found`, and watch it fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Prune `./lost+found` in each `find` of the digest script.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Name the left-out `lost+found` in `k8s/README.md` (Move a volume to another node, step 5).
  - Verification: `$ uv run devops ci docs`
