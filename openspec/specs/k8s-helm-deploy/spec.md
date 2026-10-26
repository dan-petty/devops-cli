# k8s-helm-deploy Specification

## Purpose
Automated Helm release deployment, version verification, state recovery, and resource ownership adoption for Kubernetes stacks.

## Requirements

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

### Requirement: Kubectl version skew notification
Before deploying stack resources or applying Helm releases, the deployment process SHALL check whether the locked `kubectl` version is outside the supported minor version skew of the Kubernetes API server. If a skew is detected, the deployment SHALL print a warning message naming both versions and the supported range, and continue deployment.

#### Scenario: Skew detected before deployment
- **WHEN** `devops k8s deploy-stack` runs against a cluster whose API server minor differs from the locked `kubectl` minor by more than one
- **THEN** a warning message naming both versions and the supported range is emitted and the deployment continues

#### Scenario: No skew detected
- **WHEN** `devops k8s deploy-stack` runs against a cluster whose API server is within one minor version of the locked `kubectl`
- **THEN** no version skew warning is printed
