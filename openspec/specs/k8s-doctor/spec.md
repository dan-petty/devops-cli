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
The doctor SHALL evaluate version skew between the `kubectl` on PATH, the API server, and node kubelets according to the Kubernetes version skew policy. It SHALL take the kubectl version from `clientVersion.gitVersion` of `kubectl version --client -o json`, without the leading `v`, and from no pin. Skew exceeding supported limits SHALL produce warning findings.

#### Scenario: Kubectl version skew exceeds one minor version
- **WHEN** the minor version of the `kubectl` on PATH differs from the API server minor version by more than one
- **THEN** doctor generates a cluster warning finding naming both versions and the supported server version range

#### Scenario: Kubectl version matches supported skew
- **WHEN** the minor version of the `kubectl` on PATH is within one minor of the API server minor version
- **THEN** doctor generates no version skew finding for `kubectl`

#### Scenario: The doctor reads the installed kubectl
- **WHEN** a fake `kubectl` answers `version --client -o json` with `{"clientVersion":{"gitVersion":"v1.31.2"}}` and the API server is at `v1.37.0`
- **THEN** the snapshot holds `1.31.2` and the kubectl finding names `kubectl version: 1.31.2`

#### Scenario: No kubectl states its version
- **WHEN** `kubectl version --client -o json` fails
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
