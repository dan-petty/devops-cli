# k8s-stack-help Specification

## Purpose
The Kubernetes stack commands display CLI help that dynamically includes every accepted stack value.

## Requirements

### Requirement: Stack option help names all supported stacks
The `--stack` option help for Kubernetes stack commands SHALL name every valid stack configured in `VALID_STACKS`.

#### Scenario: Display deploy-stack help
- **WHEN** user executes `devops k8s deploy-stack --help`
- **THEN** the `--stack` option description lists every stack in `VALID_STACKS`

#### Scenario: Display teardown-stack help
- **WHEN** user executes `devops k8s teardown-stack --help`
- **THEN** the `--stack` option description lists every stack in `VALID_STACKS`

#### Scenario: Display port-forward help
- **WHEN** user executes `devops k8s port-forward --help`
- **THEN** the `--stack` option description lists every stack in `VALID_STACKS`
