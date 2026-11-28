# local-path-volume-placement Specification

## Purpose
Where the pods that mount local-path claims run, so that their volumes bind on nodes with disk headroom and not on the control-plane node, and the warning before the disk of a node with local-path volumes reaches the kubelet's image garbage collection threshold.

## Requirements

### Requirement: A volume move refuses a move that cannot run safely
`devops k8s volume move <namespace>/<claim>` SHALL only read until every check passes. When a check fails, it SHALL raise `VolumeMoveRefusedError` (error code `K8S_VOLUME_MOVE_REFUSED`, exit code 1) that names each problem, and SHALL send no request that changes the cluster.

#### Scenario: A precondition fails
- **WHEN** the claim is `Pending`, or no pod mounts it, or its volume is on a worker node and neither `--to-node` nor `--storage-class` is given, or `--to-node` names a control-plane node or no node, or `--to-node` names the node of the volume and the move keeps the class, or the StatefulSet has `persistentVolumeClaimRetentionPolicy.whenScaled: Delete`, or a pod `<claim>-src` of an earlier move exists
- **THEN** the plan raises `VolumeMoveRefusedError` that names the problem, and the cluster gets no request that changes it

#### Scenario: The target class cannot hold the volume
- **WHEN** `--storage-class` names a StorageClass that does not exist, or `--to-node` names a node whose CSINode does not list the CSI driver of the class
- **THEN** the plan raises `VolumeMoveRefusedError` that names the class or the node, and the cluster gets no request that changes it

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
The run SHALL make `<claim>-move`, `<claim>-copy` and the pod `<claim>-dst` on the target node, scale the workloads to zero, start `<claim>-src` with the old claim read-only, and copy with GNU tar from pod to pod over the pod network. No exec stream SHALL carry the data. When the copy fails, it SHALL empty `/dst` and copy one more time. It SHALL compare the entries, the files, the bytes of regular files, a metadata digest and a content digest of the two sides.

#### Scenario: A dropped copy
- **WHEN** the first copy fails with `connection reset by peer`
- **THEN** the run empties `/dst`, copies one more time, and goes on

#### Scenario: The copy sends no data through an exec stream
- **WHEN** a move runs its copy
- **THEN** one bash script reads the IP address of `<claim>-dst`, starts the listener in `<claim>-dst`, runs `tar -C /src --numeric-owner --sparse -cpf -` in `<claim>-src` with its output on `/dev/tcp/<ip>/7373`, and waits for the exit code of the extract, and no `kubectl exec` of the script has `-i`

### Requirement: A volume move binds the claim to the new volume
After the two sides are equal, the run SHALL set the two volumes to `Retain`, delete the copy pods and `<claim>-copy`, save the old claim to a file, delete it, delete `<claim>-move`, reserve its volume for the claim name, and make the claim again with `spec.volumeName`. The create SHALL leave out the last-applied annotation and the annotations of the volume controllers, and the run SHALL then put the saved last-applied value back.

#### Scenario: A full move
- **WHEN** a move of `monitoring/grafana` runs and every request succeeds
- **THEN** the requests that change the cluster are, in order, the three pauses, the three creates, the scale to zero, the source pod, the copy, the two `Retain` patches, the delete of the copy pods, the delete of `<claim>-copy`, the delete of the claim, the delete of `<claim>-move`, the `claimRef` patch, the create of the claim, the annotate, the scale back and the three resumes
- **AND** the claim is made with the `volumeName` of the new volume and without the last-applied annotation, and the annotate puts back the saved value

### Requirement: A volume move starts the workloads on the target node and resumes Argo CD
After the claim is bound again, the run SHALL scale the workloads back to their replicas, and make sure that each pod that mounts the claim runs. When the move keeps the class, each pod SHALL run on the target node. The run SHALL then resume the paused Applications in reverse order, and print the old volume and the command that deletes it.

#### Scenario: The summary
- **WHEN** a move of `monitoring/grafana` succeeds
- **THEN** the command exits 0 and prints the target node and `kubectl patch pv <old-volume>` with the reclaim policy `Delete`

#### Scenario: A pod of a class change runs on another node
- **WHEN** a move to the class `longhorn` succeeds and the scheduler starts the pod of the workload on a node that is not the target node
- **THEN** the run resumes the paused Applications and the command exits 0

### Requirement: A failure before the old claim is deleted undoes the move
A failure before the run sends the delete of the old claim, an interrupt included, SHALL run the undo of each change of the move, the last change first, and SHALL raise `VolumeMoveError` (error code `K8S_VOLUME_MOVE_FAILED`) that names each undo step that failed. The run SHALL add each undo before it sends the change. The undo of `<claim>-move` SHALL read its volume when it runs, set the reclaim policy of that volume to `Delete`, and then delete the claim.

#### Scenario: The two sides are different
- **WHEN** the content digest of `/dst` differs from that of `/src`
- **THEN** the run deletes the source pod, scales the workload back, deletes the destination pod and `<claim>-copy`, sets the volume of `<claim>-move` to `Delete`, deletes `<claim>-move`, and resumes the Applications in reverse order, and the old claim stays

#### Scenario: A second dropped copy
- **WHEN** the copy fails two times
- **THEN** the run undoes the move as above

#### Scenario: A class that binds before the pod and retains its volumes
- **WHEN** the class of `<claim>-move` binds it at once and has the reclaim policy `Retain`, and the create of `<claim>-dst` fails
- **THEN** the undo sets the volume of `<claim>-move` to `Delete` before it deletes `<claim>-move`, so no volume of the move stays

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

### Requirement: A product pod on a claim requires a node off the control plane
Each pod of a manifest of `k8s/devops/` that mounts a PersistentVolumeClaim SHALL have a required node affinity in which every node selector term holds the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`.

#### Scenario: A pod on a claim
- **WHEN** a person lists the pods of namespace `devops` that mount a claim with `kubectl get pods -n devops -o json`
- **THEN** each such pod has the required node affinity
- **AND** an affinity that holds the expression only as a preference, or not in each required term, does not count

### Requirement: A volume move can change the storage class of the claim
`devops k8s volume move <namespace>/<claim> --storage-class <class>` SHALL make the claim `<claim>-move` and the claim made again with the class `<class>`. A class equal to the class of the old claim SHALL be a move that keeps the class. `--plan` SHALL print the class of the old claim and the target class.

#### Scenario: The plan of a class change
- **WHEN** the plan of `monitoring/grafana`, a `local-path` claim, runs with `--storage-class longhorn`
- **THEN** the step that makes `grafana-move` names the class `longhorn`, and the claim made again has `storageClassName: longhorn` and the `volumeName` of the new volume

#### Scenario: The dry run of a class change
- **WHEN** `devops k8s volume move monitoring/grafana --storage-class longhorn --dry-run` runs
- **THEN** no process starts, and the printed requests read the StorageClass `longhorn`, the CSIDriver of its provisioner and the CSINodes before the free disk of the nodes

### Requirement: A class change picks a node that can attach the class
With a class change and without `--to-node`, the plan SHALL pick, from the worker nodes that are Ready and schedulable and can attach a volume of the class, the node with the most `node.fs.availableBytes`. When a CSIDriver has the name of the provisioner of the class, a node SHALL attach the class only when its CSINode lists that driver. A provisioner without a CSIDriver SHALL not limit the nodes. The node of the old volume SHALL be a candidate.

#### Scenario: One worker node has the CSI driver
- **WHEN** the CSIDriver `driver.longhorn.io` exists, the class `longhorn` has that provisioner, and only the CSINode of the worker node with 1.0 TB free lists it
- **THEN** the plan names that worker node, and not the worker node with 1.7 TB free

#### Scenario: The volume is on a worker node
- **WHEN** the volume of the claim is on a worker node and `--storage-class` is given without `--to-node`
- **THEN** the plan picks a target node and does not refuse the move

### Requirement: The comparison of a volume move leaves out the top-level lost+found
The digest script of a volume move SHALL leave out the top-level `lost+found` of each side in each count and each digest. It SHALL count a directory with that name lower in the tree.

#### Scenario: A new ext4 volume
- **WHEN** a move copies a `local-path` claim to a new volume of the class `longhorn`, whose filesystem root holds an empty `lost+found`
- **THEN** the two sides have the same entries, files, bytes, metadata digest and content digest, and the move goes on

### Requirement: The copy pods of a volume move reach each other through a NetworkPolicy of the move
The run SHALL make the NetworkPolicy `<claim>-copy`, which selects the pods with the labels of the copy pods and allows them ingress from and egress to those pods on TCP port 7373 only, before it makes `<claim>-dst`. It SHALL delete the policy with the copy pods, and the undo SHALL delete it. The plan SHALL refuse a `<claim>-copy` of an earlier move as a leftover.

#### Scenario: A namespace that refuses traffic by default
- **WHEN** the namespace of the claim has a NetworkPolicy that selects every pod and allows no ingress and no egress
- **THEN** the source copy pod reaches the listener of the destination copy pod on port 7373, and the copy ends

### Requirement: A volume move leaves out the pods that have ended
The plan SHALL leave out a pod that mounts the claim and whose phase is `Succeeded` or `Failed`. The stop step SHALL not wait for it, and the check after the start SHALL not read it.

#### Scenario: A pod that a node shutdown ended
- **WHEN** a pod of an old ReplicaSet of the workload names the claim and has the phase `Succeeded`, next to the Running pod
- **THEN** the plan names only the Running pod, the stop step waits only for it, and the move ends

### Requirement: A volume move can change the access mode of the claim
`devops k8s volume move <namespace>/<claim> --access-mode <mode>` SHALL make `<claim>-move` and the claim made again with `accessModes: [<mode>]`. A mode equal to the access modes of the old claim SHALL be a move that keeps them, and a mode that Kubernetes does not name SHALL be refused. `--plan` SHALL print the access modes before and after the move.

#### Scenario: A claim of two Deployments becomes ReadWriteMany
- **WHEN** a move of a `local-path` claim that two Deployments mount runs with `--storage-class longhorn --access-mode ReadWriteMany`
- **THEN** the move claim and the claim made again have `accessModes: [ReadWriteMany]`, and the pods of the two Deployments can run on two storage nodes

#### Scenario: An unknown access mode
- **WHEN** the move runs with `--access-mode ReadWriteSome`
- **THEN** the plan raises `VolumeMoveRefusedError` that names the four access modes, and the cluster gets no request that changes it

### Requirement: A volume move waits for the running syncs of the paused Applications
After the pause, and again before the delete of the copy pods, the run SHALL end each sync operation of a paused Application whose phase is `Running` or `Terminating`, by a patch of `status.operationState.phase` to `Terminating`, and SHALL wait up to 600 s for the phase `Failed`. An operation that still runs after the wait SHALL fail the step before the point of no return.

#### Scenario: A sync that still runs after the pause
- **WHEN** the paused Applications have a sync operation in the phase `Running`, with or without `finishedAt`
- **THEN** the run ends each of them and waits for the phase `Failed`, after the pause and again before the delete of the copy pods, and only then deletes the old claim

#### Scenario: A sync that does not end
- **WHEN** the wait for an ended sync operation times out and its phase is still `Running`
- **THEN** the run raises `VolumeMoveError`, undoes its steps, resumes the Applications, and does not delete the old claim

#### Scenario: A sync that ends by itself during the wait
- **WHEN** the operation ends in another phase than `Failed` before the end takes effect
- **THEN** the wait times out, the phase is no longer `Running`, and the move goes on

### Requirement: A volume move deletes the ended pods of the claim before the old claim
Right before the delete of the old claim, the run SHALL read the pods that name the claim in their volumes and have the phase `Succeeded` or `Failed`, and SHALL delete them, so that the claim protection lets the delete of the claim end.

#### Scenario: An ended pod of an old ReplicaSet
- **WHEN** a pod of an old ReplicaSet names the claim and has the phase `Succeeded`
- **THEN** the run deletes that pod after the copy pods and before the old claim, and the move ends

### Requirement: A volume move can make the new claim larger
`devops k8s volume move <namespace>/<claim> --size <quantity>` SHALL make `<claim>-move` and the claim made again with that storage request. The plan SHALL refuse a size that is not a Kubernetes quantity or that is under the size of the old claim, and a size equal to it SHALL be a move that keeps the size. `--plan` SHALL print the size before and after the move.

#### Scenario: Data larger than the claim
- **WHEN** a `local-path` claim of 1Gi holds 1.2 GiB, and the move runs with `--storage-class longhorn --size 2Gi`
- **THEN** both new claims request 2Gi, the copy fits, and the two sides are equal

#### Scenario: A smaller size
- **WHEN** the move of a claim of 5Gi runs with `--size 1Gi`
- **THEN** the plan raises `VolumeMoveRefusedError` that names both sizes, and the cluster gets no request that changes it
