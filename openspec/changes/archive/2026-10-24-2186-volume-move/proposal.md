# Proposal

## Why

Issue #2186: `k8s/README.md` (Local-Path Volume Placement, "Move a volume to another node") gave ten hand steps to move the data of a `local-path` claim to a volume on another node. Three moves of #1634 went through them on 2026-10-24, with two surprises: an exec stream stopped (`connection reset by peer`), and `kubectl create` with the whole saved claim wrote `volumeName` into the last-applied annotation, so Argo CD refused the next sync (`spec is immutable after creation`). The owner's own run of the steps failed at the first line, because one placeholder broke the shell paste and each later command ran with empty values. #2147 still needs three moves (Grafana, the Prometheus server, Loki). The owner (2026-10-24): "most of this should be managed with infra code and devops cli functionality".

## What Changes

- New command `devops k8s volume move <namespace>/<claim> [--to-node <node>] [--plan] [--dry-run] [--context <ctx>]`, in the `devops k8s volume` group. It reads the claim, its volume, the nodes, the pods that mount the claim (from the pod specs), their Deployments or StatefulSets and the Argo CD Applications that track them. Without `--to-node` it picks the worker node with the most free disk from the kubelet's `/stats/summary`. It refuses a claim that is not `Bound`, a volume that is not on the control-plane node when no `--to-node` is given, a target on a control-plane node or on the node of the volume, a StatefulSet that deletes its claims on scale-down, and the leftovers of an earlier move.
- The move pauses Argo CD from the top down (`bootstrap`, `cluster`, the Application), makes the claim `<claim>-move` and the pod `<claim>-dst` on the target node, scales the workloads to zero, starts `<claim>-src` with the old claim read-only, copies with GNU tar over two `kubectl exec` streams through the API server (one more time on an empty destination when the stream stops), and compares the entries, the files, the bytes of regular files, a metadata digest and a content digest. It then sets both volumes to `Retain`, saves and deletes the old claim (the point of no return), reserves the new volume for the claim name, makes the claim again without the last-applied annotation and puts the annotation back, scales the workloads back, makes sure that their pods run on the target node, and resumes Argo CD.
- Before the point of no return, a failure undoes each change of the move, the last first. After it, a failure leaves Argo CD paused and prints the saved claim and the steps that did not run.
- `--plan` only reads, and prints each step with the real names. `--dry-run` makes no request, and prints the requests of a move with placeholders.
- `ProcessFake.run` records the `input` that `run_subprocess` sends as the call's `stdin`. Before, the body went into `**kwargs` and was lost, so no test could read what a `kubectl create -f -` sent.
- The name of the last-applied annotation moves from `src/devops_cli/k8s/secret_push.py` to `CONST_K8S_LAST_APPLIED_ANNOTATION` in `src/devops_cli/config/constants.py`, which both modules use.
- `k8s/README.md` replaces the ten hand steps with the command, a short list of what it does, the point of no return, and how to finish a move that stopped after that point.
- The command, its output and its refusals are observable behavior, so the change has a spec delta: ADDED requirements in the capability `local-path-volume-placement`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: adds the volume move.

## Impact

- `src/devops_cli/k8s/volume_move.py` (new), `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/exceptions/k8s.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/k8s/secret_push.py`.
- `tests/test_k8s_volume_move.py` (new), `tests/support/fakes/process.py`, `tests/test_process_contract.py`.
- `k8s/README.md`, and the generated `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/k8s.md` and `docs/ERRORS.md`.
- The cluster: nothing until a person runs a move. #2147 runs the three moves with the command.

## Feasibility

Checked on 2026-10-24 against the homelab cluster (k3s v1.31.4, Argo CD v3.5.3, k3s's local-path provisioner) with read-only commands, and kubectl client v1.37.1:

- Claims and volumes. `kubectl get pvc -o json`: `monitoring/grafana` (5Gi), `monitoring/prometheus-server` (20Gi) and `logging/storage-loki-0` (20Gi) are `Bound`, in StorageClass `local-path` (`WaitForFirstConsumer`, reclaim policy `Delete`), and their volumes have reclaim policy `Retain` and the node affinity `kubernetes.io/hostname In [<control-plane-node>]`.
- Workloads. `kubectl get pods -A -o json`: the pods that mount the three claims belong to the ReplicaSets of the Deployments `grafana` and `prometheus-server` (strategy `Recreate`), and to the StatefulSet `loki` (`persistentVolumeClaimRetentionPolicy` `whenDeleted: Retain`, `whenScaled: Retain`).
- Argo CD tracking. `application.resourceTrackingMethod` is not set in `argocd-cm`, so Argo CD v3 tracks by the annotation `argocd.argoproj.io/tracking-id`. The claims `grafana` and `prometheus-server` carry it (`grafana:/PersistentVolumeClaim:monitoring/grafana`). `storage-loki-0` comes from a claim template and does not carry it, but its StatefulSet does (`loki:apps/StatefulSet:logging/loki`). So the command reads the Application from the claim and from each workload. Each Application has `spec.syncPolicy.automated.enabled: true`.
- Free disk. `kubectl get --raw /api/v1/nodes/<node>/proxy/stats/summary` returns `node.fs.availableBytes`: about 1.7 TB, 1.6 TB and 0.8 TB on the worker nodes, 47 GB on the control-plane node. `--raw` with `-o json` fails (`--raw and --output are mutually exclusive`), so the read has no `-o`.
- kubectl behavior. `kubectl wait --for=delete pod/<missing>` exits 0, and `kubectl get pod/<a> pvc/<b> --ignore-not-found -o name` prints nothing and exits 0 for missing objects, so the waits and the leftover check need no special case. The StatefulSet `loki` has the update strategy `RollingUpdate`, but a StatefulSet with `OnDelete` refuses `kubectl rollout status`, so the command waits for `.status.readyReplicas` with `kubectl wait --for=jsonpath`.
- Pod security. The namespaces `monitoring` (`privileged`) and `logging` (`baseline`) admit a root pod with the default capabilities, which GNU tar needs to keep the owners.
- The procedure. The three moves of #1634 (Pyroscope, Qdrant, Open WebUI) ran the same steps by hand with equal digests on the two sides; their results are in `openspec/changes/archive/2026-10-24-1634-volumes-off-control-plane/tasks.md`. The digest script of the command gave equal results on a local directory and its GNU tar copy (sparse file, symbolic link, mode 700 directory), and a different metadata digest after a `chmod` of the copy.
- The command. `devops k8s volume move <claim> --plan` ran read-only for the three claims: each plan picks the same worker node with the most free disk, finds the workload, and pauses `bootstrap`, `cluster` and the Application (`grafana`, `prometheus`, `loki`).

## Existing Tool Considered

- `pv-migrate` (utkuozdemir/pv-migrate), release v3.7.0 of 2026-10-23, copies data from one existing claim to another existing claim with rsync over SSH. Its strategies are `mount` (one pod mounts the two claims, which two local volumes on different nodes cannot do), `clusterip`, `loadbalancer` and `nodeport` (pod to pod; since v3.7.0 it makes an allow-all NetworkPolicy for its own pods by default, which opens the perimeter of `monitoring` and `logging` during the copy), and `local` (port-forward and an SSH reverse tunnel through the workstation, the same path as the exec streams of GNU tar). It installs a Helm release with an sshd and an rsync image (`pv-migrate-sshd`, `pv-migrate-rsync`) for each run, and it is a new binary on the workstation. Its documentation describes no claim creation on a chosen node, no scale of the workloads, no Argo CD pause, no comparison of the two sides, and no bind of the original claim name to the new volume. So it would replace one step, the copy, and the steps that carry the risk (the pause, the scale, the bind, the annotation, the undo) would still be code. The command keeps GNU tar from the stock `debian:trixie-slim` image for the copy, which the #1634 moves used, with no network change.
- Velero restores to another node only through a file system backup in an object store, with a server in the cluster. Neither is installed, and it does not move a claim in place.
- Build cost (AGENTS.md rule 3): about 500,000 tokens and 2.5 hours to build, with the tests; about 20,000 tokens a year to keep it current with kubectl and Argo CD; about 50,000 tokens to fix it when kubectl, local-path or Argo CD changes the behavior that it relies on.
- The change deletes the ten hand steps of `k8s/README.md`. No code is replaced: before, the procedure was prose only.
