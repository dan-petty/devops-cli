# Tasks

## 1. Copy with pv-migrate

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write the tests of the pv-migrate call and its values, `--non-root` in a namespace that enforces `restricted`, the refusals (no pv-migrate, no `fsGroup`, a class with no `fsGroup`), the cleanup of a stopped copy, the eleven steps and the dry run, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Replace the copy pods, the NetworkPolicy, the tar copy, the retry and the compare with the pv-migrate call, add the Pod Security read and its refusals, and delete the tests of the deleted code.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Delete the copy measure and the copy image template

Kind: other.

Changes: `src/devops_cli/k8s/volume_move_measure.py`, `tests/k8s/test_k8s_volume_measure.py`, `tests/module_durations.json`, `k8s/devops/volume-move.yaml`, `k8s/devops/kustomization.yaml`, `tests/gate/k8s_checks/devops_runtime.py`.

- [x] 2.1 Delete `volume_move_measure.py`, its tests and its duration, the CronJob `devops/volume-move` and its image check in the gate.
  - Verification: `$ ! git grep -n -e volume_move_measure -e read_volume_move_image -e CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT -- src tests/k8s k8s`

## 3. Documents

Kind: documents.

- [x] 3.1 Update `k8s/README.md` (Move a volume to another node), `docs/HOMELAB_REPO_SWITCH.md` and the generated command reference.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- dan-petty/devtools#118 installs pv-migrate in the devtools image.
- Pending a person: after a devcontainer has pv-migrate, one live move of a test claim in a namespace that enforces `restricted`, to `--storage-class longhorn`, with a byte compare of the two volumes.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
