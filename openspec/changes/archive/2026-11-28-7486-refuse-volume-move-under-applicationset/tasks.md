# Tasks

## 1. Refuse an ApplicationSet-owned Application that overwrites the pause

Kind: behavior.

Reads: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/k8s/test_k8s_volume_move.py`.

Changes: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/lang/en/messages.py`, `tests/k8s/test_k8s_volume_move.py`.

- [x] 1.1 Write failing tests in `tests/k8s/test_k8s_volume_move.py` for an ApplicationSet-owned Application without a pause ignore, with covering pointers (`/spec/syncPolicy`, `/spec/syncPolicy/automated`, `/spec/syncPolicy/automated/enabled`), with non-covering pointers or mismatched Application names, and for the `dry_run_volume_move` read order.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Check ApplicationSet `ownerReferences` and `spec.ignoreApplicationDifferences` in `src/devops_cli/k8s/volume_move.py`, add the refusal message in `src/devops_cli/lang/en/messages.py`, and list the conditional `get applicationset` read in `_dry_run_reads`.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. Documents

Kind: documents.

Reads: `k8s/README.md`.

Changes: `k8s/README.md`.

- [x] 2.1 Note the ApplicationSet `ignoreApplicationDifferences` check in `k8s/README.md` (`Move a volume to another node`).
  - Verification: `$ uv run devops ci docs`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
