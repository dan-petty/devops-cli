# Tasks

## 1. The source of the copy holds until the destination has ended (behavior)

- [x] 1.1 Write the failing tests `test_the_source_of_the_copy_holds_until_the_destination_ended` and `test_the_copy_makes_the_pipe_that_holds_the_source_and_removes_it`, and change `test_the_copy_pipes_gnu_tar_between_the_two_pods_through_the_api_server`, in `tests/k8s/test_k8s_volume_move.py`
  - Verification: `uv run devops ci test tests/k8s/test_k8s_volume_move.py`
- [x] 1.2 Change `_copy_argv` in `src/devops_cli/k8s/volume_move.py`: the source runs `tar ... && exec cat` with `kubectl exec -i`, and a named pipe joins the stdout of the destination to the stdin of the source
  - Verification: `uv run devops ci test tests/k8s/test_k8s_volume_move.py`

## 2. The volume move section of the runbook

- [x] 2.1 State the rule in step 4 of `Move a volume to another node` in `k8s/README.md`
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- The moves of the volumes of Grafana, the Prometheus server and Loki run with the command: #2147.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
