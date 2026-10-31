# Spec Delta

## ADDED Requirements

### Requirement: docker-request-plans
Nine commands in `docker` SHALL carry the `request-plan` dry-run class: `docker build`, `docker cache`, `docker images`, `docker prune`, `docker push`, `docker sandbox`, `docker sign`, `docker stats`, and `docker verify`.
Under dry run, each command SHALL make zero external requests, execute zero daemon socket calls, invoke zero subprocesses, and output its planned requests.

#### Scenario: Dry run on docker images
- **WHEN** user executes `devops docker images --dry-run`
- **THEN** the command prints planned Docker engine image listing requests and makes zero daemon calls

#### Scenario: Dry run on docker build
- **WHEN** user executes `devops docker build . -t test:latest --dry-run`
- **THEN** the command prints planned Docker engine build requests and makes zero daemon calls

#### Scenario: Dry run on docker sign
- **WHEN** user executes `devops docker sign test:latest --key cosign.key --dry-run`
- **THEN** the command prints planned cosign sign requests and executes zero subprocesses

#### Scenario: Dry run on docker verify
- **WHEN** user executes `devops docker verify test:latest --key cosign.pub --dry-run`
- **THEN** the command prints planned cosign verify requests and executes zero subprocesses

### Requirement: sandbox-request-plans
Nine commands in `sandbox` SHALL carry the `request-plan` dry-run class: `sandbox deploy`, `sandbox exec`, `sandbox logs`, `sandbox metrics`, `sandbox network-policy`, `sandbox probe`, `sandbox status`, `sandbox stop`, and `sandbox traces`.
Under dry run, each command SHALL make zero external requests, execute zero daemon socket calls, perform zero HTTP or DNS requests, and output its planned requests.

#### Scenario: Dry run on sandbox deploy
- **WHEN** user executes `devops sandbox deploy --dry-run`
- **THEN** the command prints planned container creation and start requests and makes zero engine calls

#### Scenario: Dry run on sandbox exec
- **WHEN** user executes `devops sandbox exec ls --dry-run`
- **THEN** the command prints planned exec requests and makes zero engine calls

#### Scenario: Dry run on sandbox probe
- **WHEN** user executes `devops sandbox probe --dry-run`
- **THEN** the command prints planned HTTP health probe requests and makes zero network calls

#### Scenario: Dry run on sandbox metrics
- **WHEN** user executes `devops sandbox metrics --dry-run`
- **THEN** the command prints planned Prometheus metrics endpoint requests and makes zero network calls
