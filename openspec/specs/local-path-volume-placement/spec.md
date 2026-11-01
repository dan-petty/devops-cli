# local-path-volume-placement Specification

## Purpose
Where the pods that mount local-path claims run, so that their volumes bind on nodes with disk headroom and not on the control-plane node, and the warning before the disk of a node with local-path volumes reaches the kubelet's image garbage collection threshold.

## Requirements

### Requirement: A pod that mounts a claim does not run on the control-plane node
Each pod that mounts a claim SHALL have a required node affinity in which every node selector term holds the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`. This applies to a pod in a chart values file that an Argo CD Application installs, and to a pod in a manifest under `k8s/`. A pod in the test's table of exemptions SHALL be the only exception. Each exemption SHALL name a pod that mounts a claim and does not have that affinity.

#### Scenario: A chart pod mounts a claim
- **WHEN** a test reads the values file of each chart that an Application installs, with the claim switches and the affinity paths of that chart
- **THEN** each pod whose claim is on, and that is not exempt, has the expression in every required node selector term

#### Scenario: A manifest pod mounts a claim
- **WHEN** a test reads each workload under `k8s/` that mounts a PersistentVolumeClaim declared under `k8s/` or has a claim template
- **THEN** each such workload that is not exempt has the expression in every required node selector term of its pod spec

#### Scenario: An Application installs a chart that the test does not know
- **WHEN** an Application installs a chart that has no entry in the test's table of chart claims
- **THEN** the test fails and names the chart

#### Scenario: An exemption is stale
- **WHEN** an exemption names a pod that the test does not find, or a pod that has the affinity
- **THEN** the test fails and names the exemption

#### Scenario: Only a required term in every term counts
- **WHEN** the check reads an affinity with no node affinity, with the expression only as a preference, or with a second required term without it
- **THEN** the check reports that the pod can run on the control-plane node

### Requirement: A warning before image garbage collection on a node with local-path volumes
The Prometheus alert rules SHALL include `LocalPathNodeDiskHigh`, severity `warning`, which fires when the root filesystem of a node that runs a pod on a `local-path` claim has been over 85% used for 15 minutes. The rule SHALL join its series with `and` only, and SHALL carry the node in its `node` label.

#### Scenario: The rule reads the root filesystem of nodes with local-path pods
- **WHEN** a test reads `LocalPathNodeDiskHigh` in `k8s/monitoring/prometheus-values.yaml`
- **THEN** its expression selects `node_filesystem_avail_bytes` and `node_filesystem_size_bytes` on `mountpoint`, `kube_pod_info`, `kube_pod_spec_volumes_persistentvolumeclaims_info`, and `kube_persistentvolumeclaim_info` on `storageclass="local-path"`
- **AND** it compares with `> 0.85`, has no `group_left` or `group_right`, waits `15m`, and sets `node` from `instance`

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
The plan SHALL find the pods that mount the claim from the volumes of the pod specs, their Deployments or StatefulSets from the controller owner references, and the Argo CD Applications from the annotation `argocd.argoproj.io/tracking-id` on the claim and on each workload. It SHALL pause `bootstrap`, `cluster` and those Applications, in that order, when their automated sync is on.

#### Scenario: The plan of a Deployment's claim
- **WHEN** the plan reads `monitoring/grafana`, which a pod of the Deployment `grafana` mounts and the Application `grafana` tracks
- **THEN** the plan names the Deployment `grafana` with one replica and the pause order `bootstrap`, `cluster`, `grafana`
- **AND** `--plan` prints the thirteen steps with these names and changes nothing

### Requirement: A volume move copies the data and compares the two sides
The run SHALL make the claim `<claim>-move` and the pod `<claim>-dst` on the target node, scale the workloads to zero, start the pod `<claim>-src` with the old claim read-only, and copy with GNU tar over two `kubectl exec` streams joined by `bash -o pipefail`. When the copy fails, it SHALL empty `/dst` and copy one more time. It SHALL compare the entries, the files, the bytes of regular files, a metadata digest and a content digest of the two sides.

#### Scenario: A dropped copy
- **WHEN** the first copy fails with `connection reset by peer`
- **THEN** the run empties `/dst`, copies one more time, and goes on

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

### Requirement: version-keyed claim table
CHART_CLAIMS SHALL use a tuple of chart name and pinned version as its key type, and the set of keys SHALL equal the set returned by pinned_charts().

#### Scenario: key type and coverage check
- **WHEN** the test module is imported and CHART_CLAIMS is inspected
- **THEN** every key is a tuple of two strings, and the set of keys equals the set returned by pinned_charts()

### Requirement: version mismatch fails
A test SHALL fail when an Application pins a chart version that CHART_CLAIMS does not name.

#### Scenario: pinned version not in table
- **WHEN** pinned_charts() returns a (chart, version) pair that is not a key of CHART_CLAIMS
- **THEN** the test asserts a non-empty symmetric difference and fails
