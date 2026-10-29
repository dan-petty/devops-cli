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

### Requirement: Post-Helm custom resource CRD verification
The system SHALL check whether the cluster serves the kind of each post-Helm manifest file before executing deletion or deployment. When a cluster does not serve a post-Helm custom resource kind, `teardown-stack` SHALL skip deletion of that manifest and print a warning message. When a cluster does not serve a post-Helm custom resource kind during `deploy-stack`, the system SHALL skip applying that manifest and print a warning message.

#### Scenario: Teardown skips post-Helm manifest when CRD is not served
- **WHEN** `devops k8s teardown-stack` executes and the cluster `api-resources` does not include the manifest's kind
- **THEN** the system does not execute `kubectl delete` for that manifest, prints a warning naming the skipped manifest and unserved kind, and continues stack teardown

#### Scenario: Teardown deletes post-Helm manifest when CRD is served
- **WHEN** `devops k8s teardown-stack` executes and the cluster `api-resources` includes the manifest's kind
- **THEN** the system executes `kubectl delete -f <file> --ignore-not-found` for that manifest

#### Scenario: Deploy reports post-Helm manifest apply failure when CRD is not served
- **WHEN** `devops k8s deploy-stack` executes and the cluster `api-resources` does not include the manifest's kind
- **THEN** the system does not execute `kubectl apply` for that manifest, prints a warning naming the manifest and unserved kind, and continues stack deployment

### Requirement: deploy-stack installs each chart at the version that its Application pins
Each Helm release that `devops k8s deploy-stack` installs SHALL name a chart and a version that an Argo CD Application under `k8s/argocd/apps/` pins, so a cluster without Argo CD runs the same chart releases as the homelab.

#### Scenario: A chart update moves only the Application pin
- **WHEN** a test reads each release of `deploy-stack` and the chart sources of the Applications under `k8s/argocd/apps/`
- **THEN** each release's chart name and version are the `chart` and `targetRevision` of an Application source
