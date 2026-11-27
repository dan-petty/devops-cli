# Tasks

## 1. Move a claim to another class

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the tests of a class change and watch them fail: the plan with `--storage-class longhorn` shows the move claim and the claim made again with the class `longhorn`, picks a node that lists the CSI driver, refuses a missing class and a node without the driver, the run makes sure only that the pods run, and the dry run lists the class reads.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Add `--storage-class` to the plan, the run, the dry run and the command.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Update `k8s/README.md` (Move a volume to another node) and the generated command reference.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Done 2026-11-27: a live move of a test claim from `local-path` on a node without Longhorn to `longhorn` on the homelab. The claim name is bound to a Longhorn volume, the two sides are equal, and the pod runs on a node that the scheduler selected. The claim had no Argo CD Application, so the move paused none. A claim of 600 MiB did not pass the copy (#7408).
