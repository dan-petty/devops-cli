# local-path-volume-placement Specification

## Purpose
Where the pods that mount local-path claims run, so that their volumes bind on nodes with disk headroom and not on the control-plane node, and the warning before the disk of a node with local-path volumes reaches the kubelet's image garbage collection threshold.

## Requirements

### Requirement: A volume move refuses a move that cannot run safely
`devops k8s volume move <namespace>/<claim>` SHALL only read until every check passes. When a check fails, it SHALL raise `VolumeMoveRefusedError` (error code `K8S_VOLUME_MOVE_REFUSED`, exit code 1) that names each problem, and SHALL send no request that changes the cluster.

#### Scenario: A precondition fails
- **WHEN** the claim is `Pending`, or no pod mounts it, or its volume is on a worker node and neither `--to-node` nor `--storage-class` is given, or `--to-node` names a control-plane node or no node, or `--to-node` names the node of the volume and the move keeps the class, or the StatefulSet has `persistentVolumeClaimRetentionPolicy.whenScaled: Delete`, or a claim `<claim>-move` of an earlier move exists, or `pv-migrate` is not on `PATH`
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
- **AND** `--plan` prints the eleven steps with these names and changes nothing

### Requirement: A volume move binds the claim to the new volume
After the copy, the run SHALL set the two volumes to `Retain`, end the running syncs of the paused Applications, save the old claim to a file, delete it, delete `<claim>-move`, reserve its volume for the claim name, and make the claim again with `spec.volumeName`. The create SHALL leave out the last-applied annotation and the annotations of the volume controllers, and the run SHALL then put the saved last-applied value back.

#### Scenario: A full move
- **WHEN** a move of `monitoring/grafana` runs and every request succeeds
- **THEN** the requests that change the cluster are, in order, the three pauses, the create of `<claim>-move`, the scale to zero, the pv-migrate copy, the two `Retain` patches, the delete of the claim, the delete of `<claim>-move`, the `claimRef` patch, the create of the claim, the annotate, the scale back and the three resumes
- **AND** the claim is made with the `volumeName` of the new volume and without the last-applied annotation, and the annotate puts back the saved value

### Requirement: A volume move starts the workloads on the target node and resumes Argo CD
After the claim is bound again, the run SHALL scale the workloads back to their replicas, and make sure that each pod that mounts the claim runs. When the move keeps the class, each pod SHALL run on the target node. The run SHALL then resume the paused Applications in reverse order, and print the old volume and the command that deletes it.

#### Scenario: The summary
- **WHEN** a move of `monitoring/grafana` succeeds
- **THEN** the command exits 0 and prints the target node and `kubectl patch pv <old-volume>` with the reclaim policy `Delete`

#### Scenario: A pod of a class change runs on another node
- **WHEN** a move to the class `longhorn` succeeds and the scheduler starts the pod of the workload on a node that is not the target node
- **THEN** the run resumes the paused Applications and the command exits 0

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
- **THEN** no process starts, and the printed requests put the read of the namespace before the pause, the pause before the scale, the pv-migrate copy as root and with `--non-root`, each with its condition, after the scale, the delete of the claim before the `claimRef` patch, and the resume last

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
After the pause, and again before the delete of the old claim, the run SHALL end each sync operation of a paused Application whose phase is `Running` or `Terminating`, by a patch of `status.operationState.phase` to `Terminating`, and SHALL wait up to 600 s for the phase `Failed`. An operation that still runs after the wait SHALL fail the step before the point of no return.

#### Scenario: A sync that still runs after the pause
- **WHEN** the paused Applications have a sync operation in the phase `Running`, with or without `finishedAt`
- **THEN** the run ends each of them and waits for the phase `Failed`, after the pause and again after the copy, and only then deletes the old claim

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
- **THEN** the run deletes that pod after the `Retain` patches and before the old claim, and the move ends

### Requirement: A volume move can make the new claim larger
`devops k8s volume move <namespace>/<claim> --size <quantity>` SHALL make `<claim>-move` and the claim made again with that storage request. The plan SHALL refuse a size that is not a Kubernetes quantity or that is under the size of the old claim, and a size equal to it SHALL be a move that keeps the size. `--plan` SHALL print the size before and after the move.

#### Scenario: Data larger than the claim
- **WHEN** a `local-path` claim of 1Gi holds 1.2 GiB, and the move runs with `--storage-class longhorn --size 2Gi`
- **THEN** both new claims request 2Gi, the copy fits, and pv-migrate ends with exit code 0

#### Scenario: A smaller size
- **WHEN** the move of a claim of 5Gi runs with `--size 1Gi`
- **THEN** the plan raises `VolumeMoveRefusedError` that names both sizes, and the cluster gets no request that changes it

### Requirement: A volume move copies the data with pv-migrate
The run SHALL copy the old claim to `<claim>-move` with one `pv-migrate --strategies clusterip` call, with an `--id` of the form `volume-move-<8 hexadecimal digits>` and the Helm values on stdin (`--helm-values -`). The values SHALL put the rsync pod on the target node, and give the sshd pod the tolerations of the workload pod and of a cordon. After the copy, the run SHALL read the volume of `<claim>-move`.

#### Scenario: The copy of a move
- **WHEN** a move of `monitoring/grafana` to the worker node `worker-b` runs its copy, and the pod of the workload tolerates `example.com/dedicated`
- **THEN** pv-migrate gets the source `monitoring/grafana`, the destination `monitoring/grafana-move`, the strategy `clusterip` and the context, and its values put the rsync pod on `worker-b` and give the sshd pod the toleration of the workload pod and of a cordon

### Requirement: The undo of a stopped copy removes the objects of pv-migrate
When the run stops pv-migrate, by an interrupt or by the time bound, the undo SHALL run `pv-migrate cleanup <operation> --namespace <namespace> --force` before the other undo steps. When pv-migrate ends by itself, it removes its objects, and the undo SHALL not run `pv-migrate cleanup`.

#### Scenario: A stopped copy
- **WHEN** an interrupt or the time bound stops pv-migrate
- **THEN** the undo runs `pv-migrate cleanup` with the operation of the copy first, then the other undo steps

#### Scenario: A failed copy
- **WHEN** pv-migrate exits 23 after many lines of log
- **THEN** the undo runs no `pv-migrate cleanup`, and the error names the end of the output of pv-migrate

### Requirement: A volume move in a namespace that enforces restricted copies without root
The plan SHALL read the label `pod-security.kubernetes.io/enforce` of the namespace. When it is `restricted`, the copy SHALL add `--non-root` and `--rsync-extra-args=--no-perms`, and the plan SHALL refuse each workload whose pod template has no `fsGroup`, and a new class whose provisioner is not a CSIDriver or whose CSIDriver has `fsGroupPolicy: None`. A move that keeps the class SHALL read the class of the old claim. `--plan` SHALL print whether pv-migrate runs as root or with `--non-root`.

#### Scenario: A move to longhorn in a restricted namespace
- **WHEN** the namespace enforces `restricted`, the Deployment sets an `fsGroup`, and the move runs with `--storage-class longhorn`, whose CSIDriver has `fsGroupPolicy: ReadWriteOnceWithFSType`
- **THEN** the pv-migrate call ends with `--non-root --rsync-extra-args=--no-perms`

#### Scenario: A workload with no fsGroup
- **WHEN** the namespace enforces `restricted` and the pod template of the Deployment has no `fsGroup`
- **THEN** the plan raises `VolumeMoveRefusedError` that names the namespace and the Deployment, and the cluster gets no request that changes it

#### Scenario: A class that gives no fsGroup
- **WHEN** the namespace enforces `restricted` and the move keeps the class `local-path`, or the CSIDriver of the new class has `fsGroupPolicy: None`
- **THEN** the plan raises `VolumeMoveRefusedError` that names the namespace and the class, and the cluster gets no request that changes it

### Requirement: A failure before the old claim is deleted undoes each step of the move
A failure before the run sends the delete of the old claim, an interrupt included, SHALL run the undo of each change of the move, the last change first, and SHALL raise `VolumeMoveError` (error code `K8S_VOLUME_MOVE_FAILED`) that names each undo step that failed. The run SHALL add each undo before it sends the change. The undo of `<claim>-move` SHALL read its volume when it runs, set the reclaim policy of that volume to `Delete`, and then delete the claim.

#### Scenario: The copy fails
- **WHEN** pv-migrate exits with an error
- **THEN** the run scales the workload back, sets the volume of `<claim>-move` to `Delete`, deletes `<claim>-move`, and resumes the Applications in reverse order, and the old claim stays

#### Scenario: A class that binds before the copy and retains its volumes
- **WHEN** the class of `<claim>-move` binds it at once and has the reclaim policy `Retain`, and the scale to zero fails
- **THEN** the undo sets the volume of `<claim>-move` to `Delete` before it deletes `<claim>-move`, so no volume of the move stays

### Requirement: A volume move refuses an Application that an ApplicationSet restores
For each Argo CD Application that the move would pause, the plan SHALL check `metadata.ownerReferences` for an `argoproj.io/v1alpha1` `ApplicationSet`. When one owns the Application and its `spec.ignoreApplicationDifferences` does not cover `/spec/syncPolicy/automated/enabled` for that Application, the plan SHALL raise `VolumeMoveRefusedError` naming the ApplicationSet and `/spec/syncPolicy`, and SHALL change nothing.

#### Scenario: Owned Application without a pause ignore
- **WHEN** `plan_volume_move` reads an Application that it would pause, owned by an `ApplicationSet` whose `spec.ignoreApplicationDifferences` holds only `/spec/source/kustomize/images`
- **THEN** the plan raises `VolumeMoveRefusedError` naming the ApplicationSet and `/spec/syncPolicy`
- **AND** the cluster gets no request that changes it

#### Scenario: ApplicationSet ignores the pause field
- **WHEN** `plan_volume_move` reads an Application that it would pause, owned by an `ApplicationSet` whose `spec.ignoreApplicationDifferences` covers `/spec/syncPolicy` or `/spec/syncPolicy/automated/enabled` for that Application
- **THEN** the plan includes the Application in `paused` and returns the move plan without refusal

#### Scenario: Application without an ApplicationSet owner
- **WHEN** `plan_volume_move` reads an Application whose `metadata.ownerReferences` holds no `ApplicationSet`
- **THEN** the plan pauses and moves the Application without reading any `ApplicationSet`
