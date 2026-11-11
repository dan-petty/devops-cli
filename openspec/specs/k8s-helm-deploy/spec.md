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

### Requirement: deploy-stack deploys the chat stack
The stack `chat` SHALL install Helm release `mattermost-operator`, and apply post-Helm kustomization `k8s/mattermost` after the Helm releases complete. The CloudNativePG operator that the `Cluster` of that kustomization needs SHALL be a release of stack `infra`.

#### Scenario: deploy-stack installs chat releases and post-helm kustomization
- **WHEN** a test reads the Helm releases and the post-Helm paths that `deploy-stack` has for stack `chat`
- **THEN** the releases are `mattermost-operator` and not `cloudnative-pg`, and the post-Helm path is kustomization `mattermost`

### Requirement: deploy-stack installs the CloudNativePG operator with stack infra and applies the gateway database after the Helm releases
The stack `infra` SHALL install Helm release `cloudnative-pg` after `prometheus-operator-crds`. The stack `llm` SHALL apply `k8s/llm/gateway-db.yaml` as a post-Helm path, so the CloudNativePG CRD exists when the `Cluster` is applied. No other stack SHALL list the release.

#### Scenario: The operator has one stack and the database follows the Helm releases
- **WHEN** a test reads the Helm releases and the post-Helm paths of `deploy-stack`
- **THEN** `cloudnative-pg` is a release of stack `infra` only, and `llm/gateway-db.yaml` is a post-Helm path of stack `llm`

### Requirement: deploy-stack dry run lists the Helm repository commands
The dry run of `devops k8s deploy-stack` SHALL list, in the key `helm_commands` of its `details`, each `helm repo add <name> <url>` command of the selected stacks, in order, and then `helm repo update`, as argument lists. It SHALL list none of them for a stack without a repository. The dry run SHALL run no `helm` command.

#### Scenario: The logging stack dry run lists the repository add and update
- **WHEN** `devops k8s deploy-stack --stack logging --dry-run` runs
- **THEN** the first two entries of `details.helm_commands` are `["helm", "repo", "add", "grafana-community", "https://grafana-community.github.io/helm-charts"]` and `["helm", "repo", "update"]`

### Requirement: deploy-stack dry run lists the Helm upgrade commands
The dry run of `devops k8s deploy-stack` SHALL list, in `details.helm_commands` after the repository commands, one `helm upgrade --install` command for each release of the selected stacks, in the order of the real run. Each command SHALL carry the release name, the chart, the version, the namespace and the values file. It SHALL carry `--kube-context <context>` when a context is set, and `--wait --timeout <timeout>` when the run waits.

#### Scenario: The logging stack dry run lists the loki upgrade with chart and version
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --dry-run` runs
- **THEN** the last entry of `details.helm_commands` is `["helm", "upgrade", "--install", "--take-ownership", "loki", "grafana-community/loki", "--version", "20.0.2", "--namespace", "logging", "--values", "k8s/logging/loki-values.yaml", "--kube-context", "ctx-example", "--wait", "--timeout", "10m"]`

#### Scenario: A dry run with no wait lists no wait flag
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --no-wait --dry-run` runs
- **THEN** the last entry of `details.helm_commands` holds neither `--wait` nor `--timeout`

### Requirement: The Helm commands of a deploy-stack dry run are those of the real run
The `helm repo` and `helm upgrade` commands in `details.helm_commands` of a `devops k8s deploy-stack` dry run SHALL be built by the builders that the real run uses, so that the real run starts the same argument lists, in the same order, for the same options on Helm 3 and a cluster without unready nodes. The dry run reads no node state. For a DaemonSet release on a cluster with unready nodes, the real run omits `--wait` and the dry run lists it.

#### Scenario: The real run starts the commands that the dry run lists
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --no-wait --no-push-secrets` runs against a process double that answers Helm 3.17.0 and a ready cluster, and the same command runs with `--dry-run`
- **THEN** the `helm repo` and `helm upgrade` commands that the process double recorded equal `details.helm_commands` of the dry run

### Requirement: deploy-stack dry run lists the Helm commands as for Helm 3
The dry run of `devops k8s deploy-stack` SHALL NOT run `helm version`. It SHALL list each `helm upgrade --install` command without `--force-conflicts`, the flag that the real run adds on Helm 4 or later.

#### Scenario: The dry run starts no process
- **WHEN** `devops k8s deploy-stack --stack logging --dry-run` runs against a process double
- **THEN** the double records no `helm` command and `details.helm_commands` holds no `--force-conflicts`

### Requirement: deploy-stack installs cert-manager and the Barman Cloud plugin with stack infra after the operator
The stack `infra` SHALL install Helm release `cert-manager` in namespace `cert-manager`, and Helm release `plugin-barman-cloud` in the namespace of release `cloudnative-pg`, after both `cloudnative-pg` and `cert-manager`. No other stack SHALL list the three releases. Argo CD SHALL sync Application `plugin-barman-cloud` in a later sync wave than Application `cert-manager`.

#### Scenario: The plugin follows the operator and cert-manager in stack infra
- **WHEN** a test reads the Helm releases of `deploy-stack`
- **THEN** stack `infra` lists `cloudnative-pg` and `cert-manager` before `plugin-barman-cloud`, `plugin-barman-cloud` has the namespace of `cloudnative-pg`, and no other stack lists the three releases

#### Scenario: Argo CD syncs the plugin after cert-manager
- **WHEN** a test reads the sync waves of the Applications under `k8s/argocd/apps/`
- **THEN** the wave of `plugin-barman-cloud` is greater than the wave of `cert-manager`, and `plugin-barman-cloud` has the sync option `SkipDryRunOnMissingResource=true`
