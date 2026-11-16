# Proposal

## Why

The copy path of `devops k8s volume move` lost the end of its stream in a live move, and #3695 changed that pipe. #3701 adds the harness that measures the changed copy path on two nodes: 20 copies of 100 MiB, the digest of each side and a report. The implement job cannot reach a cluster, so a person runs the harness live in #3953 and records the numbers there.

## What Changes

- Renames the copy seam of `src/devops_cli/k8s/volume_move.py` to `copy_argv`, `digest_args` and `empty_args`, so the move and the measure build one command.
- Adds `src/devops_cli/k8s/volume_move_measure.py`: the plan of 20 copies of 104,857,600 bytes, two claims and two pods on two named nodes, the copy loop with the digest comparison, the Markdown report, the delete of the temporary namespace and a `main` entry point.
- Adds `tests/k8s/test_k8s_volume_measure.py`, which answers `run_subprocess` through the shared process fake and reaches no cluster.
- Documents the live run and the numbers that a person records in `k8s/README.md`.
- Adds seven requirements to the capability `local-path-volume-placement` for the measure, its report, its cleanup and its dry run.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: A volume move measure plans the copy command of the move, A volume move measure runs twenty copies of 100 MiB, A volume move measure places its two copy pods on two nodes, A volume move measure fails a copy whose digest differs, A volume move measure reports its complete copies and digest matches, A volume move measure removes its temporary namespace, The dry run of a volume move measure makes no request

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/k8s/volume_move_measure.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `k8s/README.md`
- Tests: `tests/k8s/test_k8s_volume_move.py`, `tests/k8s/test_k8s_volume_measure.py`

## Feasibility

- The premise of the issue holds: `k8s/devops/cronjob-runner.yaml:33:automountServiceAccountToken: false` (read with `read_file` of lines 20-40) and the runner capability table of the context lists `kubectl` as `NOT_IN_RUNNER`, so no implement step can run the 20-copy measure on a cluster.
- The probes confirm the cited paths: "The path `src/devops_cli/k8s/volume_move.py` is a file of the staging commit." and "The path `tests/k8s/test_k8s_volume_move.py` is a file of the staging commit."
- The probes stop before the identifiers: "Not probed, the bound of 10 commands is reached: `pod.nodeSelector`, `CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT`, `nodeSelector`, `_copy_argv`, `_digest_args`, `run_subprocess`, `build_kubectl_cmd`". `file_symbols` of `src/devops_cli/k8s/volume_move.py` listed `_digest_args` at line 277, `_empty_destination_args` at 292 and `_copy_argv` at 307, and `read_file` of lines 260-370 showed all three bodies, so the premise of one copy command holds.
- `references` for `_copy_argv` lists 6 files and 10 lines, `references` for `_digest_args` lists 1 file and 4 lines, and `references` for `_empty_destination_args` lists 1 file and 3 lines. Only `src/devops_cli/k8s/volume_move.py` changes; the three eval fixtures and the two archive files stay, as the `references` entries and decision 5 state.
- The staged constants that the plan relies on: `src/devops_cli/config/constants.py:4312:CONST_K8S_VOLUME_MOVE_SOURCE_DIR: Final[str] = "/src"`, `src/devops_cli/config/constants.py:4313:CONST_K8S_VOLUME_MOVE_DESTINATION_DIR: Final[str] = "/dst"`, `src/devops_cli/config/constants.py:4314:CONST_K8S_VOLUME_MOVE_LABELS: Final[dict[str, str]] = {`, `src/devops_cli/config/constants.py:4321:CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT: Final[str] = (` and `src/devops_cli/config/defaults.py:1181:DEFAULT_K8S_VOLUME_MOVE_IMAGE: str = "debian:trixie-slim"`.
- The copy path of the move: `read_file` of `src/devops_cli/k8s/volume_move.py` lines 307-365 showed the named pipe, the two `kubectl exec` streams and `bash -o pipefail`; lines 395-447 showed the destination pod sets `src/devops_cli/k8s/volume_move.py:426:spec["nodeSelector"] = {CONST_K8S_HOSTNAME_LABEL: plan.target_hostname}` and the source pod sets no nodeSelector, because its claim is already bound.
- The measure's claims name a storage class: `src/devops_cli/k8s/volume_move.py:388:"storageClassName": plan.storage_class,` shows the move takes it from the plan, and the option `--storage-class` defaults to `local-path`, the class that the stack claims use (`k8s/README.md:34:A storage layer that serves the`).
- The plan answers the unknown-command finding: it adds no `devops` subcommand, so no citation names a command that the staged CLI does not hold. The harness is the module `src/devops_cli/k8s/volume_move_measure.py`, run with python -m devops_cli.k8s.volume_move_measure, and its dry run makes no request.
- The plan answers the module-test finding: group 3 changes `src/devops_cli/lang/en/messages.py` and lists `tests/roadmap/implement/test_roadmap_implement_amend.py` in `reads`, the one test that holds `tests/roadmap/implement/test_roadmap_implement_amend.py:5:from devops_cli.lang.en.messages import MESSAGES`.
- Precondition of `plan_measure`, `copy_argv`, `digest_args` and `empty_args`: a checkout of the repository only, because each builds a manifest or an argv and starts no process.
- Precondition of `run_measure`, and of `main` for a run: a network to the API server of a cluster and a client, kubectl, from the kubeconfig of the person; the tests answer `run_subprocess` through `tests/support/fakes/process.py`, so no group reaches a cluster.
- The program that the plan introduces is the measure module, run by `python`, which the runner image holds; it starts `kubectl`, which is `NOT_IN_RUNNER` ("Only the `k8s` row runs it, to render the manifests of `k8s/`."), and the pod settings that apply are `k8s/devops/cronjob-runner.yaml:33:automountServiceAccountToken: false`, `readOnlyRootFilesystem: true` and `runAsNonRoot: true`. No verify of a group runs the measure.
- The failure classes of the verifies: `uv run devops ci test` fails as `test` with action `repair`, and `uv run devops ci docs` fails as `lint` with action `repair`.
- First checks against the real system: `uv run devops ci test tests/k8s/test_k8s_volume_move.py` passes on the base and after group 1; `uv run devops ci test tests/k8s/test_k8s_volume_measure.py` fails on the base with a missing `devops_cli.k8s.volume_move_measure` and passes after group 2; `uv run devops ci docs` passes after group 5.
- The live measure is a step of a person: no tool of this run reached a cluster, and the runner holds no kubectl. A person runs `uv run python -m devops_cli.k8s.volume_move_measure --source-node node-a --target-node node-b` and records 20/20 complete copies and 20/20 digest matches in #3953. Not checked: the free disk of the two nodes and the storage class of the cluster.

## Existing Tool Considered

No open, maintained tool covers a reliability harness for this project's own copy path: the alternatives check of 2026-11-08 recorded not-applicable for a test item and named no tool. The change builds the 20-copy loop, the random source, the digest comparison, the cleanup and the Markdown report: about 80k tokens to build, keep and fix, and about 1 day. It deletes no internal code.

## Dependencies

None.
