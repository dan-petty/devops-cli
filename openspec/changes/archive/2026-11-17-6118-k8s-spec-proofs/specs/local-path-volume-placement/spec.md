## REMOVED Requirements

### Requirement: A pod that mounts a claim does not run on the control-plane node
**Reason**: Its scenarios named a test that reads each chart values file and each workload under `k8s/`, with a table of exemptions in the test. That test asserts values of manifests. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "A pod on a claim requires a node off the control plane" holds the same rule, and names its two exemptions.

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: A warning before image garbage collection on a node with local-path volumes
The Prometheus alert rules SHALL include `LocalPathNodeDiskHigh`, severity `warning`, which fires when the root filesystem of a node that runs a pod on a `local-path` claim has been over 85% used for 15 minutes. The rule SHALL join its series with `and` only, and SHALL carry the node in its `node` label.

#### Scenario: The rule reads the root filesystem of nodes with local-path pods
- **WHEN** a person runs `uv run devops prometheus rules` and `uv run devops prometheus query 'ALERTS{alertname="LocalPathNodeDiskHigh"}'`
- **THEN** the group `homelab-storage` holds the alerting rule `LocalPathNodeDiskHigh` with the health `ok`
- **AND** the query returns a series only for a node that runs a pod on a `local-path` claim and whose root file system has been over 85% used for 15 minutes, and each series has the label `node`
