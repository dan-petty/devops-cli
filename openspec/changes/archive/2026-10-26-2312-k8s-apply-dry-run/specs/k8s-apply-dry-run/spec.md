# k8s-apply-dry-run Specification

## Purpose
Defines how `devops k8s apply` behaves under dry run: it renders a preview of the planned `kubectl apply` and starts no child process.

## ADDED Requirements

### Requirement: Dry run starts no kubectl
The system SHALL render a dry-run preview for `devops k8s apply` and SHALL NOT start a child process when `--dry-run` or the dry-run environment is set.

#### Scenario: Option dry run
- **WHEN** the user runs `devops k8s apply manifest.yaml --dry-run`
- **THEN** the command prints the dry-run preview, starts no kubectl child process and exits 0

#### Scenario: Template option dry run
- **WHEN** the user runs `devops k8s apply manifest.yaml --template --domain example.com --dry-run`
- **THEN** the command prints the dry-run preview, starts no kubectl child process and exits 0

#### Scenario: Environment dry run
- **WHEN** `DEVOPS_CLI_DRY_RUN` is true and the user runs `devops k8s apply manifest.yaml`
- **THEN** the command prints the dry-run preview, starts no kubectl child process and exits 0
