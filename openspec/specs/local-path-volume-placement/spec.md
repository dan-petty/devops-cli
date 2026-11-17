# local-path-volume-placement Specification

## Purpose
Where the pods that mount local-path claims run, so that their volumes bind on nodes with disk headroom and not on the control-plane node, and the warning before the disk of a node with local-path volumes reaches the kubelet's image garbage collection threshold.

## Requirements

### Requirement: A warning before image garbage collection on a node with local-path volumes
The Prometheus alert rules SHALL include `LocalPathNodeDiskHigh`, severity `warning`, which fires when the root filesystem of a node that runs a pod on a `local-path` claim has been over 85% used for 15 minutes. The rule SHALL join its series with `and` only, and SHALL carry the node in its `node` label.

#### Scenario: The rule reads the root filesystem of nodes with local-path pods
- **WHEN** a person runs `uv run devops prometheus rules` and `uv run devops prometheus query 'ALERTS{alertname="LocalPathNodeDiskHigh"}'`
- **THEN** the group `homelab-storage` holds the alerting rule `LocalPathNodeDiskHigh` with the health `ok`
- **AND** the query returns a series only for a node that runs a pod on a `local-path` claim and whose root file system has been over 85% used for 15 minutes, and each series has the label `node`

### Requirement: A volume move refuses a move that cannot run safely
`devops k8s volume move <namespace>/<claim>` SHALL only read until every check passes. When a check fails, it SHALL raise `VolumeMoveRefusedError` (error code `K8S_VOLUME_MOVE_REFUSED`, exit code 1) that names each problem, and SHALL send no request that changes the cluster.

#### Scenario: A precondition fails
- **WHEN** the claim is `Pending`, or no pod mounts it, or its volume is on a worker node and `--to-node` is not given, or `--to-node` names a control-plane node, the node of the volume or no node, or the StatefulSet has `persistentVolumeClaimRetentionPolicy.whenScaled: Delete`, or a pod `<claim>-src` of an earlier move exists
- **THEN** the plan raises `VolumeMoveRefusedError` that names the problem, and the cluster gets no request that changes it

### Requirement: A volume move takes a namespace/claim reference
The command SHALL take the claim as `<namespace>/<claim>`, with a valid Kubernetes name on each side. Any other reference SHALL exit 2 and start no process.

#### Scenario: The reference is not namespace/claim
- **WHEN** the command gets `grafana`, `monitoring/grafana/extra` or `Monitoring/grafana`
- **THEN** it exits 2 and starts no process

### Requirement: A volume move picks the worker node with the most free disk
Without `--to-node`, the plan SHALL pick, from the worker nodes that are Ready and schedulable, the node with the most `node.fs.availableBytes` in the kubelet's `/api/v1/nodes/<node>/proxy/stats/summary`. With `--to-node`, the plan SHALL take that node.

#### Scenario: Two worker nodes
- **WHEN** the volume of `monitoring/grafana` is on the control-plane node and two worker nodes have 1.0 TB and 1.7 TB free
- **THEN** the plan names the worker node with 1.7 TB

### Requirement: A volume move finds its workloads and Applications in the cluster
The plan SHALL find the pods that mount the claim from the volumes of the pod specs, their Deployments or StatefulSets from the controller owner references, and the Argo CD Applications from the annotation `argocd.argoproj.io/tracking-id` on the claim and on each workload. It SHALL pause the root Applications of the setting `argocd.root_applications` (default `bootstrap`, `cluster`), in their order, and then those Applications, when their automated sync is on.

#### Scenario: The plan of a Deployment's claim
- **WHEN** the plan reads `monitoring/grafana`, which a pod of the Deployment `grafana` mounts and the Application `grafana` tracks
- **THEN** the plan names the Deployment `grafana` with one replica and the pause order `bootstrap`, `cluster`, `grafana`
- **AND** `--plan` prints the thirteen steps with these names and changes nothing

### Requirement: A volume move copies the data and compares the two sides
The run SHALL make the claim `<claim>-move` and the pod `<claim>-dst` on the target node, scale the workloads to zero, start the pod `<claim>-src` with the old claim read-only, and copy with GNU tar over two `kubectl exec` streams joined by `bash -o pipefail`. When the copy fails, it SHALL empty `/dst` and copy one more time. It SHALL compare the entries, the files, the bytes of regular files, a metadata digest and a content digest of the two sides.

#### Scenario: A dropped copy
- **WHEN** the first copy fails with `connection reset by peer`
- **THEN** the run empties `/dst`, copies one more time, and goes on

### Requirement: The copy of a volume move keeps its source open until the destination has ended
The source side of the copy SHALL run `cat` after GNU tar succeeds, and a named pipe SHALL join the stdout of the destination side to the stdin of the source side. So the stdout of the source stays open until the destination has ended, and a slower destination loses no data. Bash SHALL make the named pipe and remove it on exit.

#### Scenario: The source holds until the destination ended
- **WHEN** a move runs its copy
- **THEN** the source side runs `tar -C /src --numeric-owner --sparse -cpf - . && exec cat` with `kubectl exec -i`, and reads its stdin from the named pipe
- **AND** the destination side writes its stdout to the same named pipe

### Requirement: A volume move binds the claim to the new volume
After the two sides are equal, the run SHALL set the two volumes to `Retain`, save the old claim to a file, delete it, delete `<claim>-move`, reserve its volume for the claim name, and make the claim again with `spec.volumeName`. The create SHALL leave out the last-applied annotation and the annotations of the volume controllers, and the run SHALL then put the saved last-applied value back.

#### Scenario: A full move
- **WHEN** a move of `monitoring/grafana` runs and every request succeeds
- **THEN** the requests that change the cluster are, in order, the three pauses, the two creates, the scale to zero, the source pod, the copy, the two `Retain` patches, the delete of the copy pods, the delete of the claim, the delete of `<claim>-move`, the `claimRef` patch, the create of the claim, the annotate, the scale back and the three resumes
- **AND** the claim is made with the `volumeName` of the new volume and without the last-applied annotation, and the annotate puts back the saved value

### Requirement: A volume move starts the workloads on the target node and resumes Argo CD
After the claim is bound again, the run SHALL scale the workloads back to their replicas, make sure that each pod that mounts the claim runs on the target node, and resume the paused Applications in reverse order. It SHALL print the old volume and the command that deletes it.

#### Scenario: The summary
- **WHEN** a move of `monitoring/grafana` succeeds
- **THEN** the command exits 0 and prints the target node and `kubectl patch pv <old-volume>` with the reclaim policy `Delete`

### Requirement: A failure before the old claim is deleted undoes the move
A failure before the run sends the delete of the old claim, an interrupt included, SHALL run the undo of each change of the move, the last change first, and SHALL raise `VolumeMoveError` (error code `K8S_VOLUME_MOVE_FAILED`) that names each undo step that failed. The run SHALL add each undo before it sends the change.

#### Scenario: The two sides are different
- **WHEN** the content digest of `/dst` differs from that of `/src`
- **THEN** the run deletes the source pod, scales the workload back, deletes the destination pod and `<claim>-move`, and resumes the Applications in reverse order, and the old claim stays

#### Scenario: A second dropped copy
- **WHEN** the copy fails two times
- **THEN** the run undoes the move as above

### Requirement: A failure after the old claim is deleted leaves Argo CD paused
A failure from the delete request of the old claim on SHALL resume no Application, and SHALL raise `VolumeMoveStrandedError` (error code `K8S_VOLUME_MOVE_STRANDED`) with the saved claim file, the paused Applications, the old and the new volume, and the steps that did not run.

#### Scenario: The claim cannot be made again
- **WHEN** the create of the claim fails after the old claim was deleted
- **THEN** no Application is resumed, and the error names the saved claim, `bootstrap`, `cluster` and the Application, and the last three steps

#### Scenario: The pod does not run on the target node
- **WHEN** the pod of the workload runs on another node after the move
- **THEN** no Application is resumed, and the error names the last two steps

### Requirement: The dry run of a volume move makes no request
`devops k8s volume move --dry-run` SHALL start no process, and SHALL print the requests of a move, in order, with a placeholder for each value that a read gives.

#### Scenario: A dry run
- **WHEN** `devops k8s volume move monitoring/grafana --dry-run` runs
- **THEN** no process starts, and the printed requests put the pause before the scale, the copy before the comparison, the delete of the claim before the `claimRef` patch, and the resume last

### Requirement: The source copy pod tolerates a cordon
`devops k8s volume move` SHALL give the source copy pod a toleration of `node.kubernetes.io/unschedulable` with `operator: Exists` and `effect: NoSchedule`, in addition to the tolerations of the workload pod.

#### Scenario: A move off a cordoned node
- **WHEN** the source node is cordoned and its workload pod holds no toleration for the unschedulable taint
- **THEN** the source copy pod schedules on that node and the move completes

### Requirement: A volume move measure plans the copy command of the move
The measure SHALL plan each copy with `copy_argv` and SHALL compare the two sides with `digest_args` and the digest script `CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT`.

#### Scenario: The measure plans the copy command of the move
- **WHEN** The measure plans one copy in its temporary namespace
- **THEN** The planned command holds the named pipe and the two exec streams, and each side is read with the digest script

### Requirement: A volume move measure runs twenty copies of 100 MiB
The measure SHALL make 20 copies of 104,857,600 bytes of random source data, one after another, and SHALL write fresh random data to the source claim before each copy.

#### Scenario: Twenty copies of 100 MiB
- **WHEN** The measure plans its copies with no option
- **THEN** The plan holds 20 copies of 104857600 bytes

### Requirement: A volume move measure places its two copy pods on two nodes
The measure SHALL run its source pod on the node that `--source-node` names and its destination pod on the node that `--target-node` names, each through a nodeSelector on the hostname label, and SHALL refuse two equal node names.

#### Scenario: Each copy pod selects its node
- **WHEN** The measure renders its two pods for the source node node-a and the target node node-b
- **THEN** The source pod selects node-a, the destination pod selects node-b, and the plan refuses node-a as both nodes

### Requirement: A volume move measure fails a copy whose digest differs
The measure SHALL compare the content digest of each copy's source with the content digest of its destination, and the report SHALL fail when the two differ.

#### Scenario: A mismatch fails the report
- **WHEN** The report reads 20 complete copies and one destination digest differs from its source
- **THEN** The report exits non-zero and names the mismatched copy

### Requirement: A volume move measure reports its complete copies and digest matches
The report of the measure SHALL print a Markdown table with the number of complete copies and the number of digest matches, and the run SHALL exit non-zero when fewer than 20 copies complete with a matching digest.

#### Scenario: All copies match
- **WHEN** The report reads 20 complete copies whose digests match
- **THEN** The report prints 20/20 complete copies and 20/20 digest matches, and the run exits 0

#### Scenario: One copy is short
- **WHEN** The report reads 19 complete copies and one short copy
- **THEN** The run exits non-zero and names the short copy

### Requirement: A volume move measure removes its temporary namespace
The measure SHALL create one temporary namespace and SHALL delete it when the run ends, whether the copies passed or failed.

#### Scenario: A failed copy still cleans up
- **WHEN** A copy fails during a run against the fake cluster
- **THEN** The run sends the delete of the temporary namespace and exits non-zero

### Requirement: The dry run of a volume move measure makes no request
The dry run of the measure SHALL start no process and SHALL print the requests of a run in order.

#### Scenario: The dry run lists the requests
- **WHEN** The dry run runs for two named nodes
- **THEN** It prints the create of the namespace, the two claims, the two pods and the 20 copies, and it starts no process

### Requirement: A pod on a claim requires a node off the control plane
Each pod that mounts a claim SHALL have a required node affinity in which every node selector term holds the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`. This applies to a pod of a chart that an Argo CD Application installs, and to a pod of a manifest under `k8s/`. The pods of the CloudNativePG Clusters `mattermost/mattermost-db` and `llm/llm-gateway-db` SHALL be the only exemptions.

#### Scenario: A pod on a claim
- **WHEN** a person lists the pods that mount a PersistentVolumeClaim with `kubectl get pods --all-namespaces -o json`
- **THEN** each such pod, other than a pod of the two exempt Clusters, has a required node affinity in which every node selector term holds `node-role.kubernetes.io/control-plane` `DoesNotExist`
- **AND** an affinity that holds the expression only as a preference, or not in each required term, does not count

#### Scenario: An exempt Cluster
- **WHEN** a person runs `kubectl -n mattermost get pods -o wide` and `kubectl -n llm get pods -o wide`
- **THEN** the pods of `mattermost-db` and `llm-gateway-db` run on the node of their claims, because a claim of each Cluster is on the control-plane node and the pod stays `Pending` with the affinity
- **AND** #3803 moves the volume of `mattermost-db`, and a follow-up of #3782 moves the volume of `llm-gateway-db`, and each move then adds the affinity and ends the exemption

#### Scenario: Grafana, the Prometheus server and Loki keep off the control-plane node
- **WHEN** a person runs `kubectl -n monitoring get pods -o wide` and `kubectl -n logging get pods -o wide`
- **THEN** the pods of Grafana, of the Prometheus server and of Loki run on nodes that have no label `node-role.kubernetes.io/control-plane`
