# Tasks

## 1. Share the copy command and the digest arguments of the copy path

Kind: behavior. Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`. Changes: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`.

- [ ] 1.1 Write `tests/k8s/test_k8s_volume_move.py::test_the_copy_command_comes_from_copy_argv` first: it fails on the base because `copy_argv` does not exist, and it pins that the copy stream of the move runs the command that `copy_argv` builds for the namespace, the two pods and the context
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py` fails on the base
- [ ] 1.2 Rename `_copy_argv` in `src/devops_cli/k8s/volume_move.py` to `copy_argv(namespace, source_pod, destination_pod, context)`, rename `_digest_args` to `digest_args`, and rename `_empty_destination_args` to `empty_args(pod, namespace)`. Update the callers in `_MoveRun._stream`, `_MoveRun.copy`, `_MoveRun._side` and `_dry_run_copy` of the same file. Keep the named pipe, the two `kubectl exec` streams and `bash -o pipefail` unchanged
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py` passes

## 2. Plan the measure: two pods on two nodes and twenty copies of 100 MiB

Kind: behavior. Reads: `src/devops_cli/k8s/volume_move.py`, `tests/k8s/test_k8s_volume_move.py`, `tests/support/fakes/process.py`. Changes: `src/devops_cli/k8s/volume_move_measure.py` (new), `tests/k8s/test_k8s_volume_measure.py` (new).

- [ ] 2.1 Write `tests/k8s/test_k8s_volume_measure.py::test_the_measure_plans_the_copy_command_of_the_move` first: it fails on the base because the module does not exist. The module also holds `test_the_measure_plans_twenty_copies_of_100_mib`, `test_each_copy_pod_selects_its_node` and `test_the_measure_pods_carry_no_service_account_token`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_measure.py` fails on the base
- [ ] 2.2 Add `src/devops_cli/k8s/volume_move_measure.py` with `MeasurePlan`, `plan_measure`, `claim_manifests`, `pod_manifests`, `random_data_args` and `measure_requests`. `plan_measure` takes the source node, the target node and the storage class, refuses two equal node names, and holds `MEASURE_COPIES` of 20 and `MEASURE_BYTES` of 104857600. Each claim names the storage class and requests 1Gi. Each pod selects its own node on `CONST_K8S_HOSTNAME_LABEL`, mounts its claim read-write at `CONST_K8S_VOLUME_MOVE_SOURCE_DIR` or `CONST_K8S_VOLUME_MOVE_DESTINATION_DIR`, sets `automountServiceAccountToken: False`, and runs `DEFAULT_K8S_VOLUME_MOVE_IMAGE` with `sleep infinity`. `measure_requests` lists the namespace, the two claims, the two pods, each write of random data, each `copy_argv` call, each `digest_args` call and the delete of the namespace. The tests answer `run_subprocess` through `tests/support/fakes/process.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_measure.py` passes

## 3. Run the measure, compare each digest and report the counts

Kind: behavior. Reads: `src/devops_cli/k8s/volume_move_measure.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/support/fakes/process.py`, `tests/k8s/test_k8s_volume_measure.py`. Changes: `src/devops_cli/k8s/volume_move_measure.py`, `tests/k8s/test_k8s_volume_measure.py`, `src/devops_cli/lang/en/messages.py`.

- [ ] 3.1 Write `tests/k8s/test_k8s_volume_measure.py::test_a_failed_copy_still_removes_the_namespace` first: it fails on the base because the run deletes no namespace. The module also holds `test_a_mismatch_fails_the_report`, `test_all_copies_match` and `test_one_short_copy_fails_the_report`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_measure.py` fails on the base
- [ ] 3.2 Add `CopyRun`, `run_measure`, `render_report` and `report_problems` to `src/devops_cli/k8s/volume_move_measure.py`. `run_measure` creates the namespace, the two claims and the two pods, waits for both pods, and makes each copy: it writes 104857600 bytes of random data to the source with `random_data_args`, empties the destination with `empty_args`, runs `copy_argv`, and reads `digest_args` on both sides. A copy whose command fails or whose digests differ is recorded and the run goes on. A `finally` sends the delete of the temporary namespace. `render_report` prints the Markdown table with a row for the complete copies and a row for the digest matches, and `report_problems` returns one problem for each copy that did not complete or match, and one when fewer than 20 completed. Add the report and failure messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_measure.py` passes

## 4. Add the entry point and the dry run of the measure

Kind: behavior. Reads: `src/devops_cli/k8s/volume_move_measure.py`, `tests/k8s/test_k8s_volume_measure.py`, `tests/support/fakes/process.py`. Changes: `src/devops_cli/k8s/volume_move_measure.py`, `tests/k8s/test_k8s_volume_measure.py`.

- [ ] 4.1 Write `tests/k8s/test_k8s_volume_measure.py::test_the_dry_run_lists_the_requests` first: it fails on the base because the module has no entry point. It asserts that the dry run prints the requests and starts no process through `tests/support/fakes/process.py`, and that `main` returns 1 for a report that holds a problem
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_measure.py` fails on the base
- [ ] 4.2 Add `main(argv)` to `src/devops_cli/k8s/volume_move_measure.py` with `--source-node`, `--target-node`, `--context`, `--storage-class` and `--dry-run`, and the `if __name__ == "__main__"` call. The storage class defaults to `local-path`. It builds the plan with `plan_measure`, prints the requests of `measure_requests` for a dry run, and otherwise runs `run_measure`, prints the report and returns 1 with each problem of `report_problems`. The test answers `run_subprocess` through `tests/support/fakes/process.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_measure.py` passes

## 5. Document the live measure in the k8s guide

Kind: other. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 5.1 Add a subsection Measure the copy path under the volume move section of `k8s/README.md`: the module and its options, the two nodes, the 20 copies of 100 MiB of random data, the digest of each side, the rule of 20 complete copies with a matching digest, the temporary namespace that the run deletes, and the step of the person who runs it and records 20/20 complete copies and 20/20 digest matches in #3953
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `k8s/README.md` with the live measure and the numbers that a person records in #3953
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
