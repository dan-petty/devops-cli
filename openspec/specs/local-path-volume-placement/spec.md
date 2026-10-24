# local-path-volume-placement Specification

## Purpose
Where the pods that mount local-path claims run, so that their volumes bind on nodes with disk headroom and not on the control-plane node, and the warning before the disk of a node with local-path volumes reaches the kubelet's image garbage collection threshold.

## Requirements

### Requirement: A pod that mounts a claim does not run on the control-plane node
Each pod that mounts a claim, in a chart values file that an Argo CD Application installs or in a manifest under `k8s/`, SHALL have a required node affinity in which every node selector term holds the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`. A pod in `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` SHALL be the only exception, and each exemption SHALL name a pod that mounts a claim and does not have that affinity.

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
- **WHEN** the check reads an affinity with no node affinity, with the expression only as a preference, or with a second required term without the expression
- **THEN** the check reports that the pod can run on the control-plane node

### Requirement: A warning before image garbage collection on a node with local-path volumes
The Prometheus alert rules SHALL include `LocalPathNodeDiskHigh`, severity `warning`, which fires when the root filesystem of a node that runs a pod on a `local-path` claim has been over 85% used for 15 minutes. The rule SHALL join its series with `and` only, and SHALL carry the node in its `node` label.

#### Scenario: The rule reads the root filesystem of nodes with local-path pods
- **WHEN** a test reads `LocalPathNodeDiskHigh` in `k8s/monitoring/prometheus-values.yaml`
- **THEN** its expression selects `node_filesystem_avail_bytes` and `node_filesystem_size_bytes` on `mountpoint`, `kube_pod_info`, `kube_pod_spec_volumes_persistentvolumeclaims_info`, and `kube_persistentvolumeclaim_info` on `storageclass="local-path"`
- **AND** it compares with `> 0.85`, has no `group_left` or `group_right`, waits `15m`, and sets `node` from `instance`
