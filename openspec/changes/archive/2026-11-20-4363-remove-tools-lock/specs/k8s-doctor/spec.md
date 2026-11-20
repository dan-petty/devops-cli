## MODIFIED Requirements

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
