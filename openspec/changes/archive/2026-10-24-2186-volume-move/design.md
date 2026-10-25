# Design

## Context

The ten hand steps of `k8s/README.md` (Local-Path Volume Placement) move the data of a `local-path` claim to a new volume on another node. The order matters: Argo CD must not start the workload during the copy, the old claim must not be deleted before the two sides are equal, and after the old claim is deleted a self-heal must not make an empty claim. The command does the same steps, checks each one, and undoes its own changes when a step fails before the old claim is deleted.

## Decisions

### Every request goes through `run_subprocess`

Each kubectl request goes through `run_subprocess` (ARCHITECTURE.md, section 3), so the shared process fake answers it in the tests and the subprocess spans record it. The copy joins two `kubectl exec` streams with one pipe: `bash -o pipefail -c "<source> | <destination>"`, where `shlex.join` quotes each word of the two kubectl commands and `pipefail` fails the copy when either side fails. `run_subprocess` starts one program, so bash holds the pipe, and no byte of the copy passes through Python.

Rejected alternatives:

- Two `subprocess.Popen` children joined in Python: they would bypass `run_subprocess`, its environment isolation and its spans, and the shared process fake could not answer them.
- The exec stream of the Kubernetes Python client (`kubernetes.stream`): a second edge for the same requests, with no shared fake for exec streams.
- `kubectl cp` to the workstation and back: it needs the whole volume on the workstation disk, and the extract runs as the workstation user, so the numeric owners are lost.
- A pod-to-pod copy (rsync, or `pv-migrate`): the namespaces behind a perimeter need a NetworkPolicy opening between the two pods (proposal, Existing Tool Considered).

### The copy runs again one time, on any failure

When the copy fails, the command empties `/dst` and copies one more time. It does not match the error text (`connection reset by peer`): the text of kubectl, the API server and the container runtime is an open domain, and the comparison after the copy finds a bad copy either way. A second failure stops the move and undoes it.

### The steps are one list, for the plan and for the run

`describe_volume_move` gives the text of the thirteen steps, and the run prints the same text before each step, so `--plan` shows what the run does. The ninth step deletes the old claim: `POINT_OF_NO_RETURN_INDEX`.

### Each undo is added before its change

A step adds the undo of a change before it sends the request. A request can fail after the API server made the change (a timeout, a dropped connection), and each undo is harmless when the change did not happen: a delete has `--ignore-not-found`, a scale and a patch set the value from before the move. The undo runs the last change first, reports each undo that fails, and runs the others.

### The point of no return is the delete request

The run marks the point of no return before it sends the delete of the old claim, not after: when the request fails, the claim may be deleted. From that mark on, the command resumes nothing: Argo CD stays paused, and `VolumeMoveStrandedError` names the saved claim, the two volumes and the steps that did not run. `k8s/README.md` (Finish a stopped move) tells a person how to finish.

### The plan reads the cluster, not the labels

The pods that mount the claim come from the volumes of the pod specs. Their workloads come from the controller owner references: a ReplicaSet leads to its Deployment. The Applications come from the annotation `argocd.argoproj.io/tracking-id` on the claim and on each workload, because a claim from a StatefulSet's claim template has no annotation of its own. An Application that a tracking annotation names and that does not exist is a refusal.

### Waits run in kubectl

Each wait is a `kubectl wait` with its own `--timeout`: a pod Ready, a pod gone, a claim `Bound` (`--for=jsonpath={.status.phase}=Bound`) and the workloads ready (`--for=jsonpath={.status.readyReplicas}=<n>`). The command has no sleep loop. `kubectl rollout status` is not used, because it refuses a StatefulSet with the update strategy `OnDelete`.

### The claim is made again without the controller annotations

The saved claim keeps its name, namespace, labels, owner references and spec, with `spec.volumeName` set to the new volume. The create leaves out the last-applied annotation, which `kubectl annotate` puts back after the create (#1634), and the annotations that the volume controllers write (`CONST_K8S_CLAIM_CONTROLLER_ANNOTATIONS`), which name the old binding, such as `volume.kubernetes.io/selected-node`.

### The saved claim stays on the workstation

The command saves the old claim, as the API server returned it, in `k8s/volume-move/<namespace>-<claim>-<UTC time>.json` under the data directory. A failure to write it happens before the point of no return, so it undoes the move.

## Risks

- The copy pods run as root with the default capabilities. A namespace with the Pod Security level `restricted` refuses them: the create of the destination pod fails, before the workloads stop, and the move undoes itself.
- The copy and each digest read every byte of the volume through the API server. `DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS` (one hour) bounds each one.
