## ADDED Requirements

### Requirement: The CloudNativePG maintenance window of a disruptive host
Before the drain check of a disruptive host, the command SHALL patch each 1-instance CloudNativePG cluster whose primary pod runs on the node with `spec.nodeMaintenanceWindow: {inProgress: true, reusePVC: true}` when agent access is `full`. After the uncordon, the command SHALL patch each cluster with `inProgress: false` and wait for `Cluster in healthy state` with primary Ready within `infra.node_ready_timeout_seconds`. An unhealthy cluster SHALL stop the host.

#### Scenario: A single-instance primary gets the window before the drain check and loses it after the uncordon
- **WHEN** an apply runs on node-3 where the 1-instance CloudNativePG cluster `llm/llm-gateway-db` has its primary pod
- **THEN** the maintenance window opens before the drain check, closes after the uncordon, and the apply waits for the cluster to report `Cluster in healthy state` with its primary Ready

#### Scenario: A cluster with two instances gets no window
- **WHEN** an apply runs on node-3 where the CloudNativePG cluster `db/shared-db` has 2 instances
- **THEN** no maintenance window opens for `db/shared-db`

#### Scenario: Repo agent access below full gets no window
- **WHEN** an agent applies a plan on a repo with agent access `safe`
- **THEN** no maintenance window opens

#### Scenario: An unhealthy cluster stops the host
- **WHEN** a cluster does not report `Cluster in healthy state` within `infra.node_ready_timeout_seconds` after the window closes
- **THEN** the host stops at the step `health` and leaves the node cordoned

#### Scenario: An Argo CD Application with selfHeal and no ignoreDifferences refuses the host
- **WHEN** the tracking Application of a single-instance cluster has `selfHeal: true` and no `ignoreDifferences` entry for `/spec/nodeMaintenanceWindow`
- **THEN** the host is refused before the drain check and the command names the `ignoreDifferences` remediation step

#### Scenario: A cluster manifest with nodeMaintenanceWindow in git refuses the host
- **WHEN** the manifest of the cluster in git contains `nodeMaintenanceWindow`
- **THEN** the host is refused before the drain check

#### Scenario: The dry run lists the reads and patches of the window
- **WHEN** a dry run runs on a plan of a disruptive host
- **THEN** the output lists the read of CloudNativePG clusters and the patches of the maintenance window

#### Scenario: The audit record names each cluster of the window
- **WHEN** an apply opens a maintenance window for `llm/llm-gateway-db`
- **THEN** the audit record of the host names `llm/llm-gateway-db`
