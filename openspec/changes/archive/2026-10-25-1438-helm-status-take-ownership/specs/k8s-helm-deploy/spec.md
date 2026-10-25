# Spec Delta

## Purpose

Automated Helm release deployment, version verification, state recovery, and resource ownership adoption for Kubernetes stacks.

## ADDED Requirements

### Requirement: Helm version requirement
The deployment process SHALL require Helm version 3.17 or later when deploying Helm releases. If the installed Helm version is older than 3.17, deployment SHALL abort with an error message naming the installed version.

#### Scenario: Helm version meets minimum requirement
- **WHEN** the installed Helm version is 3.17.0 or later and `devops k8s deploy-stack` runs
- **THEN** the version check succeeds and deployment continues

#### Scenario: Helm version is below minimum requirement
- **WHEN** the installed Helm version is 3.16.2 and `devops k8s deploy-stack` runs
- **THEN** deployment fails with an error stating that Helm 3.17 or later is required and naming version 3.16.2

### Requirement: Release status inspection and recovery
Before executing `helm upgrade --install`, the deployment process SHALL inspect the release status with `helm status -o json`. A release in `pending-install` status SHALL be uninstalled with `helm uninstall`. A release in `pending-upgrade` or `pending-rollback` status SHALL be rolled back with `helm rollback` before proceeding.

#### Scenario: Pending install release is uninstalled
- **WHEN** `helm status -o json` reports release status `pending-install`
- **THEN** the system executes `helm uninstall` before running `helm upgrade --install`

#### Scenario: Pending upgrade release is rolled back
- **WHEN** `helm status -o json` reports release status `pending-upgrade`
- **THEN** the system executes `helm rollback` before running `helm upgrade --install`

#### Scenario: Pending rollback release is rolled back
- **WHEN** `helm status -o json` reports release status `pending-rollback`
- **THEN** the system executes `helm rollback` before running `helm upgrade --install`

### Requirement: Helm ownership adoption
Every `helm upgrade --install` invocation SHALL include `--take-ownership` to adopt existing unmanaged Kubernetes resources without manual annotation or labeling.

#### Scenario: Upgrade command includes take-ownership
- **WHEN** `devops k8s deploy-stack` executes a Helm release install or upgrade
- **THEN** the constructed `helm upgrade --install` command arguments include `--take-ownership`
