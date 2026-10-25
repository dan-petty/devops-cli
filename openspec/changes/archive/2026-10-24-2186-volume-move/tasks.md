# Tasks

## 1. The shared process fake records the input of `run_subprocess`

- [x] 1.1 Write the failing test `test_process_fake_records_the_input_that_run_subprocess_sends` in `tests/test_process_contract.py`, and see it fail before the change with `uv run devops ci test tests/test_process_contract.py`
- [x] 1.2 Give `ProcessFake.run` (`tests/support/fakes/process.py`) the `input` parameter of the real runner, and record it as the call's `stdin`; verify with `uv run devops ci test tests/test_process_contract.py`

## 2. `devops k8s volume move`

- [x] 2.1 Write the failing tests in `tests/test_k8s_volume_move.py` on the shared process fake: the plan and its target, each refusal, a full move, the claim made again without its last-applied annotation, the copy pods and the copy pipe, a digest difference, a dropped copy, a second dropped copy, an interrupt, a failed request and a failed undo before the point of no return, a failed create and a pod on the wrong node after it, the dry run, and the command's plan, dry run, summary, refusal, stranded output and bad reference. See them fail before the change with `uv run devops ci test tests/test_k8s_volume_move.py`
- [x] 2.2 Add `src/devops_cli/k8s/volume_move.py` (plan, steps, run with undo, dry run), the exceptions `VolumeMoveError`, `VolumeMoveRefusedError` and `VolumeMoveStrandedError`, the constants, the defaults and the output strings; verify with `uv run devops ci test tests/test_k8s_volume_move.py` and `uv run mypy src/devops_cli/k8s/volume_move.py src/devops_cli/commands/k8s/volume.py src/devops_cli/exceptions/k8s.py`
- [x] 2.3 Add the command `move` to `src/devops_cli/commands/k8s/volume.py`, with `--to-node`, `--plan`, `--dry-run` and `--context`; verify with `uv run devops ci test tests/test_k8s_volume_move.py tests/test_k8s_volume_reclaim.py`
- [x] 2.4 Move the name of the last-applied annotation to `CONST_K8S_LAST_APPLIED_ANNOTATION`, and use it in `src/devops_cli/k8s/secret_push.py`; verify with `uv run devops ci test tests/test_k8s_push_secrets.py`
- [x] 2.5 Regenerate the command documents and the error table; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. The procedure in `k8s/README.md`

- [x] 3.1 Replace the ten hand steps of Local-Path Volume Placement with the command, what it does, the point of no return, and how to finish a stopped move; verify with `uv run devops docs check`
- [x] 3.2 Run the read-only plan for `monitoring/grafana`, `monitoring/prometheus-server` and `logging/storage-loki-0`; each plan picks the worker node with the most free disk and pauses `bootstrap`, `cluster` and the Application of the workload. Verify with `uv run devops k8s volume move monitoring/grafana --plan`

## Workflow follow-up

- Move the volumes of Grafana, the Prometheus server and Loki with the command, then remove their entries from `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` and add the affinity to their values: #2147.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
