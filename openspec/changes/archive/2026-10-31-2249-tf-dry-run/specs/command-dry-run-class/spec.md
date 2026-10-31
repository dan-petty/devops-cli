# Spec Delta: command-dry-run-class for OpenTofu Commands

## Added Requirements

### Requirement: tf-request-plans
Nine external-request commands in `tf` SHALL carry the `request-plan` dry-run class: `tf init`, `tf plan`, `tf apply`, `tf destroy`, `tf output`, `tf deploy-cloud`, `tf lint`, `tf cost breakdown`, and `tf cost diff`.
Under dry run, each command SHALL make zero external requests, execute zero subprocesses, and output its planned requests.

#### Scenario: Dry run on tf init
- **WHEN** user executes `devops tf init --dry-run`
- **THEN** the command prints planned init execution requests and starts no process

#### Scenario: Dry run on tf plan
- **WHEN** user executes `devops tf plan --dry-run`
- **THEN** the command prints planned plan execution requests and starts no process

#### Scenario: Dry run on tf apply
- **WHEN** user executes `devops tf apply --dry-run`
- **THEN** the command prints planned apply execution requests and starts no process

#### Scenario: Dry run on tf cost breakdown
- **WHEN** user executes `devops tf cost breakdown --dry-run`
- **THEN** the command prints planned Infracost execution requests and starts no process

### Requirement: tf-no-external-request
Six local OpenTofu commands SHALL carry the `no-external-request` dry-run class: `tf drift`, `tf fmt`, `tf graph`, `tf notify-plan`, `tf status`, and `tf validate`.
Under `devops --dry-run`, each command SHALL execute locally without external requests.
Echo-only previews and explicit `--dry-run` options SHALL be removed from read-only commands without a shim.

#### Scenario: Dry run on tf status
- **WHEN** user executes `devops --dry-run tf status`
- **THEN** the command renders local status information without external requests

#### Scenario: Dry run on tf graph
- **WHEN** user executes `devops --dry-run tf graph`
- **THEN** the command renders local dependency graph data without echo-only preview
