# Design

## Decisions

- **Deliver the harness as the module `src/devops_cli/k8s/volume_move_measure.py` with a `main` entry point, and add no `devops` subcommand.**: The copy path needs a cluster, the runner holds no kubectl, and one person runs the measure once, so a subcommand would add help text, a generated docs page and a dry-run class for a single caller.
- **Share the copy command, the digest arguments and the empty command through `copy_argv`, `digest_args` and `empty_args` in `src/devops_cli/k8s/volume_move.py`.**: The measure must exercise the pipe that #3695 changed, and a second copy of that pipe text would drift from the move.
- **Give both measure pods a nodeSelector on the hostname label, one per named node.**: Both measure claims are fresh, and local-path binds a fresh claim on the node of its first consumer, so each pod pins the node of its claim; the move's source pod needs none because its claim is already bound (`src/devops_cli/k8s/volume_move.py:426:spec["nodeSelector"] = {CONST_K8S_HOSTNAME_LABEL: plan.target_hostname}`).
- **Create one temporary namespace and delete it in a `finally`.**: One delete removes the two claims and the two pods, and a failed copy cannot leave them behind.
- **Keep the eval fixtures `tests/fixtures/roadmap_eval/completeness/change-3695-complete/draft.diff`, `tests/fixtures/roadmap_eval/completeness/change-3695-hunk-removed/case.json` and `tests/fixtures/roadmap_eval/completeness/change-3695-hunk-removed/draft.diff` unchanged.**: They are recorded drafts of past plans that `devops roadmap eval completeness` scores as data, so they are not applied to the tree and the rename of `_copy_argv` does not reach them.
- **Write fresh random data to the source and empty the destination before each copy.**: Each copy then compares 100 MiB of new content, and a stale destination cannot hide a short copy.
- **Report with a Markdown table and a non-zero exit below 20 complete copies with a matching digest.**: A person pastes the table into #3953, and the exit code makes the rule checkable without reading the table.

## Rejected alternatives

- **A `devops` subcommand for the harness.**: `k8s/devops/cronjob-runner.yaml:33:automountServiceAccountToken: false` and the runner capability table of the context list `kubectl` as `NOT_IN_RUNNER`, so the command would serve only a person at a workstation, and the staged CLI holds no such command.
- **A live pytest test that makes the 20 copies.**: `tests/k8s/test_k8s_volume_move.py:5:No test starts kubectl or bash, and no test reaches a cluster.` and the runner image holds no kubectl, so such a test would skip or fail on host state.
- **A Kubernetes Job with 20 completions.**: `k8s/devops/cronjob-runner.yaml:33:automountServiceAccountToken: false` and no kubectl in the image, so a Job pod cannot drive the two exec streams.
- **Run `devops k8s volume move` 20 times on a real claim.**: `src/devops_cli/k8s/volume_move.py:77:POINT_OF_NO_RETURN_INDEX = 8` marks the step that deletes the old claim, so 20 moves would change a live cluster 20 times.
- **Compare the two sides with md5sum or with Python hashlib over the exec stream.**: The move compares the SHA-256 content digest of `src/devops_cli/config/constants.py:4321:CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT: Final[str] = (`, and no byte of the copy passes through Python, so either choice would measure another path.
- **Reach the cluster with the Kubernetes Python client instead of kubectl.**: The copy path is two `kubectl exec` streams (`src/devops_cli/k8s/volume_move.py:def _copy_argv`), so a client would measure a path that the move does not run.

## Unchanged references

- `tests/fixtures/roadmap_eval/completeness/change-3695-complete/draft.diff` (eval fixture): It is a recorded draft of a past plan that `devops roadmap eval completeness` scores as data, so it is not applied to the tree.
- `tests/fixtures/roadmap_eval/completeness/change-3695-hunk-removed/case.json` (eval fixture): It is the case of a recorded draft that the eval scores as data, so it is not applied to the tree.
- `tests/fixtures/roadmap_eval/completeness/change-3695-hunk-removed/draft.diff` (eval fixture): It is a recorded draft of a past plan that the eval scores as data, so it is not applied to the tree.
- `openspec/changes/archive/2026-11-06-3695-volume-move-copy-end/proposal.md` (archive): The archive records the change that added the pipe, and a merged record is not edited.
- `openspec/changes/archive/2026-11-06-3695-volume-move-copy-end/tasks.md` (archive): The archive records the task that changed the copy command, and a merged record is not edited.

## Security

The measure runs kubectl with the kubeconfig of the person against the cluster that they name, and it creates one namespace, two claims and two pods on the two nodes that they name. The two pods mount a claim read-write and set `automountServiceAccountToken: False`, so no token enters a temporary pod, and they run the image of a volume move. A person confirms the cluster, the two nodes and the storage class before the run. `tests/k8s/test_k8s_volume_measure.py::test_the_measure_pods_carry_no_service_account_token` fails if a pod mounts a token, and `tests/k8s/test_k8s_volume_measure.py::test_a_failed_copy_still_removes_the_namespace` fails if the run deletes any namespace other than its own or does not delete it.
