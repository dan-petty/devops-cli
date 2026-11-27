# Tasks

## 1. Change the access mode

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the tests of the access mode in the plan, the run, the dry run, the refusal and `--plan`, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Add `--access-mode` to the plan, the run, the dry run and the command.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Describe `--access-mode` in `k8s/README.md` (Change the class of a volume) and in the generated command reference.
  - Verification: `$ uv run devops ci docs`
