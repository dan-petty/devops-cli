# k8s-doctor Specification

## Purpose
Diagnose Kubernetes cluster deployment health, collect API snapshots, verify component version skew, and recommend remediations.

## Requirements

### Requirement: Snapshot collection and dry run
The doctor SHALL collect API objects from the Kubernetes cluster into a diagnostic snapshot, including server version, nodes, pods, and events. When executed with `--dry-run`, doctor SHALL render the planned requests without contacting the cluster.

#### Scenario: Dry run lists version and cluster requests
- **WHEN** `devops k8s doctor --dry-run` is invoked
- **THEN** the request plan includes `get_code cluster`, `list_node cluster`, and workload listings without executing them

#### Scenario: Server version is captured in snapshot
- **WHEN** doctor collects cluster state from an active cluster
- **THEN** `Snapshot.server_version` contains the Kubernetes API server gitVersion string

### Requirement: Version skew diagnostic rule
The doctor SHALL evaluate version skew between the pinned `kubectl` binary, the API server, and node kubelets according to the Kubernetes version skew policy. Skew exceeding supported limits SHALL produce warning findings.

#### Scenario: Kubectl version skew exceeds one minor version
- **WHEN** the locked `kubectl` minor version differs from the API server minor version by more than one
- **THEN** doctor generates a cluster warning finding naming both versions and the supported server version range

#### Scenario: Kubectl version matches supported skew
- **WHEN** the locked `kubectl` minor version is within one minor of the API server minor version
- **THEN** doctor generates no version skew finding for `kubectl`

#### Scenario: Node kubelet is older than API server by more than three minor versions
- **WHEN** a node reports a `kubeletVersion` more than three minor versions older than the API server
- **THEN** doctor generates a cluster warning finding for that node identifying the kubelet version and the supported range

#### Scenario: Server version is empty or unavailable
- **WHEN** the cluster snapshot contains no server version
- **THEN** doctor skips version skew evaluation without raising an unhandled exception

### Requirement: The log lines of the snapshot are decoded and masked text
The doctor SHALL read the log of a flagged pod as UTF-8 text, with each line of the log as one line of the snapshot, and SHALL mask secrets in each line.

#### Scenario: A log of several lines
- **WHEN** the log of a flagged pod is the bytes of three lines, one with a check mark and one with a token
- **THEN** the snapshot holds three lines for the pod, the check mark is the character, and the token is masked
