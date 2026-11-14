# roadmap-implement-runner Specification

## ADDED Requirements

### Requirement: Repository and item labels
`build_job` SHALL set `roadmap.devops-cli/owner`, `roadmap.devops-cli/repo` and `roadmap.devops-cli/item` on the Job metadata and on the pod template metadata.

#### Scenario: Labels on the Job and on its pod
- **WHEN** `build_job` builds a runner Job for repository `Dan-Petty/DevOps-CLI` and item 4558.
- **THEN** both metadata blocks hold `roadmap.devops-cli/owner: dan-petty`, `roadmap.devops-cli/repo: devops-cli` and `roadmap.devops-cli/item: 4558`.

### Requirement: Repository annotation on the pod
`build_job` SHALL set the annotation `roadmap.devops-cli/repository` to the casefolded `owner/name` on the Job and on the pod template.

#### Scenario: The annotation reaches the pod
- **WHEN** `build_job` builds a Job for `Dan-Petty/DevOps-CLI`.
- **THEN** the Job metadata and the pod template metadata hold the annotation `roadmap.devops-cli/repository: dan-petty/devops-cli`.

### Requirement: Component and ownership labels
`build_job` SHALL set `app.kubernetes.io/component: roadmap-<row>`, `app.kubernetes.io/part-of: devops-cli-stack` and `app.kubernetes.io/managed-by: devops-cli` on the Job and on the pod template.

#### Scenario: The component of the runner Job
- **WHEN** the Service builds a runner Job for the `implement` row.
- **THEN** both metadata blocks hold `app.kubernetes.io/component: roadmap-implement` and `app.kubernetes.io/part-of: devops-cli-stack`.

### Requirement: Runner Job name
The runner Job of the Service SHALL be named `devops-cli-implement-<slug>-<item>-<6 hex>` and MUST hold 63 characters or fewer.

#### Scenario: A long slug is cut
- **WHEN** the slug and the item number make the name longer than 63 characters.
- **THEN** the name holds 63 characters, keeps the `-<6 hex>` suffix, and matches the DNS-1123 subdomain form.

### Requirement: Dry run shows the Job
`devops k8s run-job --template runner --dry-run` MUST show the Job name and the repository labels and MUST send no request.

#### Scenario: The dry run of a runner Job
- **WHEN** a user runs the command with `--repo dan-petty/devops-cli -- true`.
- **THEN** the printed plan holds the Job name placeholder and the `roadmap.devops-cli/*` labels, and no kubectl command runs.

### Requirement: Runner telemetry service name
The runner CronJob MUST set `OTEL_SERVICE_NAME` to `roadmap-implement`, and the two dashboards that name `devops-cli-job` MUST name `roadmap-implement`.

#### Scenario: The runner reports under its own service name
- **WHEN** the runner CronJob is read from `k8s/devops/cronjob-runner.yaml`.
- **THEN** its `runner` container holds `OTEL_SERVICE_NAME` with the value `roadmap-implement`.
