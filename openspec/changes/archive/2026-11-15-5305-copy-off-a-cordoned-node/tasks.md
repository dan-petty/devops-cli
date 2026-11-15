# Tasks

## 1. Tolerate the cordon

Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Update the copy-pod test and watch it fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Add the constant and the toleration.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## Workflow follow-up

- Pending a person: move the Open WebUI claim off the cordoned node with the new binary.
