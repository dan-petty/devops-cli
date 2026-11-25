## ADDED Requirements

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
