# Proposal

## Why

`devops k8s volume move` copied the data of a claim with its own code: copy pods, a NetworkPolicy, a Perl listener, GNU tar over bash `/dev/tcp`, a retry on an empty destination and a digest script in bash that compared the two sides. The command moves data, so each bug can lose data. In 30 days it got 14 bug issues and 7 fix pull requests, and about 5 of the bugs were in the copy and the compare (#3695, #5305, #7408, #7414, #7449). pv-migrate is a maintained open tool that does this copy (#7498).

## What Changes

- The copy step runs `pv-migrate --strategies clusterip` from the old claim to `<claim>-move`, with Helm values on stdin: a `nodeSelector` that puts the rsync pod on the target node, and the tolerations of the workload pod and of a cordon for the sshd pod. rsync checks each file that it sends, so the move has no compare step.
- In a namespace that enforces Pod Security `restricted`, the copy adds `--non-root`, and the plan refuses a workload with no `fsGroup` and a class whose volumes get no `fsGroup` from the kubelet. The plan prints whether the copy runs as root.
- The plan refuses a move when `pv-migrate` is not on `PATH`, and refuses `<claim>-move` of an earlier move as the only leftover.
- When the run stops pv-migrate (an interrupt or the time bound), the undo runs `pv-migrate cleanup <operation> --force` first.
- The steps go from 13 to 11: no source pod, no compare, no delete of the copy pods. The end of the running syncs before the old claim is a step of its own.
- Deleted: the copy pods, NetworkPolicy `<claim>-copy`, the listener, send, result and digest scripts, the retry, the suspended CronJob `devops/volume-move` and its image pin, and the copy measure `volume_move_measure` with its tests.
- The behavior of a devops command changes, so the change has spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: the copy of a volume move is pv-migrate; the comparison, the copy pods, the copy NetworkPolicy and the copy measure go.
- `k8s-helper-images`: no command reads an image from CronJob `devops/volume-move`.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`; deleted `src/devops_cli/k8s/volume_move_measure.py`
- Manifests: deleted `k8s/devops/volume-move.yaml`, `k8s/devops/kustomization.yaml`
- Tests: `tests/k8s/test_k8s_volume_move.py`, `tests/gate/k8s_checks/devops_runtime.py`; deleted `tests/k8s/test_k8s_volume_measure.py`
- Documents: `k8s/README.md` (Move a volume to another node), `docs/HOMELAB_REPO_SWITCH.md`, `docs/commands/k8s.md`
- The change fits one pull request. The install of pv-migrate is a change of the devtools image, in dan-petty/devtools.

## Feasibility

- pv-migrate v3.8.0 (2026-11-15), Apache-2.0, not archived, last push 2026-11-26 (GitHub API, 2026-11-28).
- `docs/cli-reference.md` at v3.8.0 names each flag of the call: `--source`, `--source-namespace`, `--dest`, `--dest-namespace`, `--strategies`, `--id`, `--helm-timeout`, `--helm-values`, `--show-progress-bar`, `--source-context`, `--dest-context`, `--non-root`, and `cleanup <operation-id> --namespace --force`.
- Helm v4.3.1, which pv-migrate v3.8.0 uses (`go.mod`), reads a values file `-` from stdin (`pkg/cli/values/options.go:120`).
- `internal/strategy/clusterip.go` installs one release with the sshd pod on the side of the source claim and the rsync Job on the side of the destination claim. The chart values `rsync.nodeSelector` and `sshd.tolerations` exist in `internal/helm/pv-migrate/values.yaml`. pv-migrate sets no node affinity for a claim that no pod mounts (`internal/pvc/info.go`, `buildAffinityHelmValues` returns nil for no node).
- `internal/strategy/strategy.go:226` (`applyNonRootValues`): `--non-root` sets `runAsNonRoot`, user and group 10000, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]` and `seccompProfile: RuntimeDefault`, and `fsGroup` 10000. `internal/rsync/cmd.go` then adds `--no-o --no-g --omit-dir-times`, so the copy keeps no owner and no group.
- `internal/migrator/migrator.go:482` (`handleMounted`) refuses a claim that a running pod mounts, and `cleanupAttempt` removes the release at the end of a run, also after a failure. `cmd/pv-migrate/main.go` cancels the run on SIGINT, but `subprocess.run` kills the child 0.25 s after an interrupt, so the undo removes the release then.
- `pv-migrate cleanup <id>` exits 1 with `no releases found for operation` when nothing is left (`internal/app/cleanup.go`), so the undo runs it only when the run stopped pv-migrate.
- A live move in a `restricted` namespace was not run: the agent of this change makes no move against the cluster.

## Existing Tool Considered

pv-migrate (github.com/utkuozdemir/pv-migrate, Apache-2.0, v3.8.0) does the copy, the per-file check, the retry, the copy pods, their NetworkPolicies and their cleanup. It does not pause Argo CD, stop the workloads, rebind the claim name or undo a failed move, so the command keeps those steps. Longhorn (deployed in dan-petty/homelab) and Velero (Apache-2.0) are in `design.md`. VolSync is AGPL-3.0, so it is not a candidate.

The change deletes this internal code: `copy_argv`, `digest_args`, `empty_args`, `read_volume_move_image`, `_copy_pod_manifest`, `_copy_policy_manifest`, `_parse_digest`, `_differences`, `CopyDigest`, the steps `start_source`, `compare` and `delete_copy_pods`, the six bash and Perl constants of the copy and the compare, `DEFAULT_K8S_VOLUME_MOVE_EXTRACT_WAIT_SECONDS`, the module `volume_move_measure.py` (561 lines), its 348 lines of tests, and the CronJob `devops/volume-move`. In `src/`, the change adds 283 lines and deletes 1,143.

## Dependencies

- dan-petty/devtools#118 installs pv-migrate in the devtools image. Until a devcontainer has that image, the plan refuses a move and names the missing command.
