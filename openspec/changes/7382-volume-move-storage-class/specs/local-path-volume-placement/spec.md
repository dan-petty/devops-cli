## MODIFIED Requirements

### Requirement: A volume move refuses a move that cannot run safely
`devops k8s volume move <namespace>/<claim>` SHALL only read until every check passes. When a check fails, it SHALL raise `VolumeMoveRefusedError` (error code `K8S_VOLUME_MOVE_REFUSED`, exit code 1) that names each problem, and SHALL send no request that changes the cluster.

#### Scenario: A precondition fails
- **WHEN** the claim is `Pending`, or no pod mounts it, or its volume is on a worker node and neither `--to-node` nor `--storage-class` is given, or `--to-node` names a control-plane node or no node, or `--to-node` names the node of the volume and the move keeps the class, or the StatefulSet has `persistentVolumeClaimRetentionPolicy.whenScaled: Delete`, or a pod `<claim>-src` of an earlier move exists
- **THEN** the plan raises `VolumeMoveRefusedError` that names the problem, and the cluster gets no request that changes it

#### Scenario: The target class cannot hold the volume
- **WHEN** `--storage-class` names a StorageClass that does not exist, or `--to-node` names a node whose CSINode does not list the CSI driver of the class
- **THEN** the plan raises `VolumeMoveRefusedError` that names the class or the node, and the cluster gets no request that changes it

### Requirement: A volume move starts the workloads on the target node and resumes Argo CD
After the claim is bound again, the run SHALL scale the workloads back to their replicas, and make sure that each pod that mounts the claim runs. When the move keeps the class, each pod SHALL run on the target node. The run SHALL then resume the paused Applications in reverse order, and print the old volume and the command that deletes it.

#### Scenario: The summary
- **WHEN** a move of `monitoring/grafana` succeeds
- **THEN** the command exits 0 and prints the target node and `kubectl patch pv <old-volume>` with the reclaim policy `Delete`

#### Scenario: A pod of a class change runs on another node
- **WHEN** a move to the class `longhorn` succeeds and the scheduler starts the pod of the workload on a node that is not the target node
- **THEN** the run resumes the paused Applications and the command exits 0

## ADDED Requirements

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
