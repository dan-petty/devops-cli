# command-dry-run-class Specification

## ADDED Requirements

### Requirement: devcontainer-request-plans
The five commands `devcontainer bootstrap-k8s`, `devcontainer post-create`, `devcontainer post-start`, `devcontainer run-lifecycle`, and `devcontainer unlock-keyring` SHALL carry the `request-plan` dry-run class. Under dry run, they execute zero subprocesses or network requests and render the planned requests.

#### Scenario: Dry run on devcontainer bootstrap-k8s
- **WHEN** user executes `devops devcontainer bootstrap-k8s --dry-run`
- **THEN** zero subprocesses execute and planned Minikube commands are printed

#### Scenario: Dry run on devcontainer post-create
- **WHEN** user executes `devops devcontainer post-create --dry-run`
- **THEN** zero network or installation subprocesses execute and planned tool installation requests are printed

#### Scenario: Dry run on devcontainer post-start
- **WHEN** user executes `devops devcontainer post-start --dry-run`
- **THEN** zero subprocesses execute and planned git and kubectl requests are printed

#### Scenario: Dry run on devcontainer run-lifecycle
- **WHEN** user executes `devops devcontainer run-lifecycle --dry-run`
- **THEN** zero lifecycle actions execute and planned lifecycle requests are printed

#### Scenario: Dry run on devcontainer unlock-keyring
- **WHEN** user executes `devops devcontainer unlock-keyring --dry-run`
- **THEN** zero subprocesses execute and planned gnome-keyring and gh auth commands are printed

### Requirement: install-tools-request-plans
The `install-tools` command SHALL carry the `request-plan` dry-run class. Under dry run, it executes zero downloads or installer subprocesses and renders the planned requests.

#### Scenario: Dry run on install-tools
- **WHEN** user executes `devops install-tools --dry-run`
- **THEN** zero HTTP requests or installer subprocesses execute and planned downloads are printed

### Requirement: devcontainer-no-external-request
The four commands `devcontainer init`, `devcontainer update`, `devcontainer list`, and `devcontainer validate` SHALL carry the `no-external-request` dry-run class. `devcontainer init` and `devcontainer update` SHALL provide local previews under `--dry-run` without modifying filesystem paths.

#### Scenario: Dry run on devcontainer init
- **WHEN** user executes `devops devcontainer init --dry-run`
- **THEN** a preview line is printed and no configuration files are created

#### Scenario: Dry run on devcontainer update
- **WHEN** user executes `devops devcontainer update --dry-run`
- **THEN** a preview line is printed and `devcontainer.json` is not modified

#### Scenario: Dry run on devcontainer list
- **WHEN** user executes `devops --dry-run devcontainer list`
- **THEN** the command executes locally and renders the devcontainer list

#### Scenario: Dry run on devcontainer validate
- **WHEN** user executes `devops --dry-run devcontainer validate`
- **THEN** the command executes locally and validates the manifest syntax

### Requirement: install-tools-no-external-request
The `install-tools status` command SHALL carry the `no-external-request` dry-run class, running locally without external requests.

#### Scenario: Dry run on install-tools status
- **WHEN** user executes `devops --dry-run install-tools status`
- **THEN** the status check executes locally without external requests
