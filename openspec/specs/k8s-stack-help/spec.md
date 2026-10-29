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

### Requirement: The stack names are declared once
The stack names SHALL be declared once, in deploy order, in `CONST_K8S_STACKS`. `_resolve_stacks` SHALL return those names for `all`, SHALL return a name of that tuple for itself, and SHALL refuse any other value. No other module SHALL declare its own list of stack names.

#### Scenario: All resolves to every declared stack
- **WHEN** `_resolve_stacks("all")` runs
- **THEN** it returns the names of `CONST_K8S_STACKS`, in their order

#### Scenario: An unknown stack is refused
- **WHEN** `_resolve_stacks("monitoring")` runs
- **THEN** it exits with status 1 and names every valid stack

### Requirement: Every help text that lists stacks names every stack
The deploy-stack summary, the `--stack` help of `devops k8s push-secrets` and the `--stack` help of `devops devcontainer bootstrap-k8s` SHALL name every stack of `CONST_K8S_STACKS` and the value `all`, and SHALL name no other stack.

#### Scenario: Display the deploy-stack summary
- **WHEN** user executes `devops k8s deploy-stack --help`
- **THEN** the summary names every stack of `CONST_K8S_STACKS` and `all`

#### Scenario: Display the push-secrets stack help
- **WHEN** user executes `devops k8s push-secrets --help`
- **THEN** the `--stack` option description names `base`, every stack of `CONST_K8S_STACKS` and `all`

#### Scenario: Display the bootstrap-k8s stack help
- **WHEN** user executes `devops devcontainer bootstrap-k8s --help`
- **THEN** the `--stack` option description names every stack of `CONST_K8S_STACKS` and `all`, and does not name `monitoring`
