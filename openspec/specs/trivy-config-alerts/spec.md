# trivy-config-alerts Specification

## Purpose
How `devops scan alerts` turns each open `Trivy-config` code scanning alert group into one issue, the daily workflow that runs it, the rule of SECURITY.md that names the judge and the time, and the ignore file that the `trivy config` scan reads.

## Requirements

### Requirement: The filer lists the open Trivy-config alerts
The alert filer SHALL list each open code scanning alert whose tool is `Trivy-config` and no other alert.

#### Scenario: A payload with a second tool
- **WHEN** the alerts payload holds three `Trivy-config` alerts and one `CodeQL` alert
- **THEN** the filer groups the three `Trivy-config` alerts and no `CodeQL` alert

### Requirement: The filer groups the alerts by rule and path
The filer SHALL group the open alerts by rule id and file path, and it SHALL put the group with the worst severity first.

#### Scenario: Two alerts of one rule in one file
- **WHEN** two open alerts hold the rule id `KSV-0017` and the path `k8s/gpu-feature-discovery/daemonset.yaml`
- **THEN** the filer gives one group, and the body of the group names both alert numbers

### Requirement: A group that an open issue names gets no new issue
The filer SHALL skip each group whose exact title an open issue holds. A pull request with that title is no issue.

#### Scenario: One group with an open issue
- **WHEN** an open issue holds the title of one group and the other group has no issue
- **THEN** the filer files one issue, for the group with no open issue

### Requirement: One run files a bounded number of issues
The filer MUST file at most five issues in one run, and it SHALL name the groups that it leaves for the next run.

#### Scenario: Eight groups with no issue
- **WHEN** eight groups have no open issue and the limit is five
- **THEN** the filer files five issues and names the three groups that it leaves for the next run

### Requirement: The filed issue holds the rule, the path and the severity
The filer SHALL put the rule id, the path, the severity and the alert numbers in the issue that it files. The title SHALL be `fix(security): judge Trivy-config <rule-id> in <path>`.

#### Scenario: The body of a filed issue
- **WHEN** the filer files an issue for the rule id `DS-0002` at `.devcontainer/Dockerfile` with the severity `HIGH`
- **THEN** the title holds `DS-0002` and `.devcontainer/Dockerfile`, and the body holds `HIGH` and the alert number

### Requirement: The workflow runs every day with the least permissions
The alert workflow MUST run on a daily schedule, with the permissions `contents: read`, `security-events: read` and `issues: write` only. It SHALL have no `workflow_run` trigger, which zizmor reports as a HIGH finding.

#### Scenario: The triggers of the workflow
- **WHEN** a test reads the `on` block of `.github/workflows/trivy-config-alerts.yml`
- **THEN** the block holds a `schedule` trigger and no `workflow_run` trigger

### Requirement: The policy names the judge and the time
`SECURITY.md` SHALL name who judges a new `Trivy-config` alert, the time in which it happens, and the ignore file with its reason and expiry fields.

#### Scenario: The Trivy-config rule in the policy
- **WHEN** a test reads the `Trivy-config` rule of `SECURITY.md`
- **THEN** the rule names the owner for a CRITICAL alert within 24 hours, an agent for the other severities within 14 days, and `.trivyignore.yaml` with `statement` and `expired_at`

### Requirement: The IaC scan reads the ignore file with an expiry
The `trivy config` scan SHALL name `.trivyignore.yaml` of its directory with `--ignorefile` when that file exists, and it SHALL name no ignore file when it does not.

#### Scenario: A directory with the file
- **WHEN** the scan starts in a directory that holds `.trivyignore.yaml`
- **THEN** the command holds `--ignorefile` and the path of that file, and Trivy hides a finding of an entry whose `expired_at` is later than today

### Requirement: The privileged GPU workload holds a dated ignore entry
The repository SHALL hold one `misconfigurations` entry of `.trivyignore.yaml` for the rule `KSV-0017` on the path `k8s/gpu-feature-discovery/daemonset.yaml`, with a `statement` that names the privileged GPU device and sysfs access of the workload and the tracking issue #5646, and an `expired_at` date no more than 3 days after the entry.

#### Scenario: The entry of the privileged GPU workload
- **WHEN** a test reads the ignore file of the repository
- **THEN** it finds one misconfiguration entry of the rule KSV-0017 and the path of the GPU feature discovery DaemonSet, and the entry holds a statement with the tracking issue #5646 and an expiry date

#### Scenario: A second entry for another rule
- **WHEN** another judged alert adds a second misconfiguration entry to the ignore file
- **THEN** the test still finds the KSV-0017 entry of the GPU feature discovery DaemonSet and passes

### Requirement: The sysfs mount of the GPU workload holds a dated ignore entry
The repository SHALL hold one `misconfigurations` entry of `.trivyignore.yaml` for the rule `KSV-0121` on the path `k8s/gpu-feature-discovery/daemonset.yaml`, with a `statement` that names the sysfs host path mount of the workload and the tracking issue #5646, and an `expired_at` date no more than 3 days after the entry.

#### Scenario: The entry of the sysfs host path mount
- **WHEN** a test reads the ignore file of the repository
- **THEN** it finds one misconfiguration entry of the rule KSV-0121 and the path of the GPU feature discovery DaemonSet, and the entry holds a statement with the tracking issue #5646 and an expiry date

#### Scenario: Existing entries for other rules
- **WHEN** another judged alert adds or keeps other misconfiguration entries in the ignore file
- **THEN** the test still finds the KSV-0121 entry of the GPU feature discovery DaemonSet and passes

### Requirement: The default pod security context of the GPU workload holds a dated ignore entry
The repository SHALL hold one `misconfigurations` entry of `.trivyignore.yaml` for the rule `KSV-0118` on the path `k8s/gpu-feature-discovery/daemonset.yaml`, with a `statement` that names the default pod security context of the workload and the tracking issue #5646, and an `expired_at` date no more than 3 days after the entry.

#### Scenario: The entry of the default pod security context
- **WHEN** a test reads the ignore file of the repository
- **THEN** it finds one misconfiguration entry of the rule KSV-0118 and the path of the GPU feature discovery DaemonSet, and the entry holds a statement with the tracking issue #5646 and an expiry date

#### Scenario: Existing entries for other rules
- **WHEN** another judged alert adds or keeps other misconfiguration entries in the ignore file
- **THEN** the test still finds the KSV-0118 entry of the GPU feature discovery DaemonSet and passes

### Requirement: The GPU feature discovery workload sets a read-only root file system
The `k8s/gpu-feature-discovery/daemonset.yaml` manifest SHALL configure `readOnlyRootFilesystem: true` in the container `securityContext` of `gpu-feature-discovery`.

#### Scenario: The manifest sets a read-only root file system
- **WHEN** a test loads `k8s/gpu-feature-discovery/daemonset.yaml` and inspects the `gpu-feature-discovery` container
- **THEN** it finds `readOnlyRootFilesystem` set to `true`, `privileged` set to `true`, and both `output-dir` and `host-sys` volumes configured

### Requirement: The harbor template Dockerfile holds a dated ignore entry
The repository SHALL hold one `misconfigurations` entry of `.trivyignore.yaml` for the rule `DS-0029` on the path `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`, with a `statement` that names the harbor task-template Dockerfile and issue #5947, and an `expired_at` date no more than 3 days after the entry.

#### Scenario: The entry of the harbor template Dockerfile
- **WHEN** a test reads the ignore file of the repository
- **THEN** it finds one misconfiguration entry of the rule DS-0029 and the path `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`, and the entry holds a statement with the issue #5947 and an expiry date
