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

### Requirement: Run the konmon orphaned check
The `devops k8s doctor` command SHALL run the `orphaned` check of the `konmon` executable on `PATH` using read-only flags (`check orphaned -o json`, plus `-n <namespace>` and `--context <context>` when provided), and `plan_doctor_requests` SHALL list the planned read-only `konmon` step.

#### Scenario: Fake konmon executable on PATH
- **WHEN** a test puts a fake `konmon` executable on `PATH` that records its arguments and exits `0`
- **THEN** the recorded arguments contain `check` and `orphaned`, `-o` `json`, and no mutating verb (`apply`, `create`, `delete`, `patch`, `replace`, `edit`, `drain`, or `scale`)

### Requirement: Map orphaned workloads to findings
The doctor report SHALL contain a `workload` finding whose `resource` is `<Kind>/<namespace>/<name>` for each `Deployment`, `StatefulSet`, `DaemonSet`, and `CronJob` in the `konmon` JSON `findings` array, and MUST drop any non-workload kind such as `Service`.

#### Scenario: Four workload kinds mapped and Service dropped
- **WHEN** `konmon check orphaned -o json` returns one `Deployment`, one `StatefulSet`, one `DaemonSet`, one `CronJob`, and one `Service`
- **THEN** the doctor report includes findings for each of the four workload resources (`Deployment/...`, `StatefulSet/...`, `DaemonSet/...`, `CronJob/...`) and omits the `Service`

### Requirement: Report missing or failed konmon checks
When `konmon` is missing from `PATH`, exits non-zero without valid findings JSON, or returns invalid JSON, the doctor report SHALL include a `cluster` warning finding naming `konmon` (and the masked error detail when failed) and MUST continue evaluating all other doctor checks.

#### Scenario: konmon absent from PATH with fake kubectl
- **WHEN** a test runs `devops k8s doctor` with a `PATH` holding no `konmon` executable and a `kubectl` returning a skewed client version against the fake cluster
- **THEN** the report contains a finding naming `konmon` and also retains the `kubectl` version skew finding

#### Scenario: konmon exits 1 with stderr failure
- **WHEN** a test puts a fake `konmon` executable on `PATH` that exits `1` and writes `permission denied` to `stderr`
- **THEN** `devops k8s doctor` exits without an unhandled exception and reports a finding containing `konmon` and `permission denied`
