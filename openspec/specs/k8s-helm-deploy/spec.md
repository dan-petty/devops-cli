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
Before deploying stack resources or applying Helm releases, the deployment process SHALL check whether the version of the `kubectl` on PATH, from `kubectl version --client -o json`, is outside the supported minor version skew of the Kubernetes API server. If a skew is detected, the deployment SHALL print a warning message naming both versions and the supported range, and continue deployment.

#### Scenario: Skew detected before deployment
- **WHEN** `devops k8s deploy-stack` runs against a cluster whose API server minor differs from the minor of the `kubectl` on PATH by more than one
- **THEN** a warning message naming both versions and the supported range is emitted and the deployment continues

#### Scenario: No skew detected
- **WHEN** `devops k8s deploy-stack` runs against a cluster whose API server is within one minor version of the `kubectl` on PATH
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
Each Helm release that `devops k8s deploy-stack` installs SHALL take its chart version from the `targetRevision` of the chart source of the Argo CD Application of the same name in the environment tree, so a cluster without Argo CD runs the same chart releases as the homelab. The code SHALL hold no chart version. A release that no Application pins SHALL stop the deploy before it touches the cluster.

#### Scenario: A chart update moves only the Application pin
- **WHEN** Renovate moves the `targetRevision` of the Application of a chart, and `deploy-stack` runs on that tree
- **THEN** the `helm upgrade --install` command of the release names the new version after `--version`, with no change of code

#### Scenario: A copy of the tree pins another version
- **WHEN** the Application `loki` of a copy of the tree pins `9.8.7`, and `devops k8s deploy-stack --stack logging --k8s-dir <copy> --dry-run` runs
- **THEN** the `helm upgrade --install` command of release `loki` holds `--version 9.8.7`

#### Scenario: No Application pins a release
- **WHEN** the tree holds no Application `loki`, and `devops k8s deploy-stack --stack logging --k8s-dir <copy> --dry-run` runs
- **THEN** the command exits 1, and the error names release `loki` and the Application folders

### Requirement: deploy-stack deploys the chat stack
The stack `chat` SHALL install Helm release `mattermost-operator`, and apply post-Helm kustomization `k8s/mattermost` after the Helm releases complete. The CloudNativePG operator that the `Cluster` of that kustomization needs SHALL be a release of stack `infra`.

#### Scenario: deploy-stack installs chat releases and post-helm kustomization
- **WHEN** a person runs `uv run devops k8s deploy-stack --stack chat --dry-run`
- **THEN** `helm_releases` is `mattermost-operator` with no `cloudnative-pg`, `post_helm` is the kustomization `k8s/mattermost`, and the command makes no request

### Requirement: deploy-stack installs the CloudNativePG operator with stack infra and applies the gateway database after the Helm releases
The stack `infra` SHALL install Helm release `cloudnative-pg` after `prometheus-operator-crds`. The stack `llm` SHALL apply `k8s/llm/gateway-db.yaml` as a post-Helm path, so the CloudNativePG CRD exists when the `Cluster` is applied. No other stack SHALL list the release.

#### Scenario: The operator has one stack and the database follows the Helm releases
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when `cloudnative-pg` is a release of stack `infra` and of no stack that holds a CloudNativePG `Cluster`, `llm/gateway-db.yaml` is a post-Helm path of stack `llm`, and the kustomization of `k8s/llm` lists the file

### Requirement: deploy-stack dry run lists the Helm repository commands
The dry run of `devops k8s deploy-stack` SHALL list, in the key `helm_commands` of its `details`, each `helm repo add <name> <url>` command of the selected stacks, in order, and then `helm repo update`, as argument lists. It SHALL list none of them for a stack without a repository. The dry run SHALL run no `helm` command.

#### Scenario: The logging stack dry run lists the repository add and update
- **WHEN** `devops k8s deploy-stack --stack logging --dry-run` runs
- **THEN** the first two entries of `details.helm_commands` are `["helm", "repo", "add", "grafana-community", "https://grafana-community.github.io/helm-charts"]` and `["helm", "repo", "update"]`

### Requirement: deploy-stack dry run lists the Helm upgrade commands
The dry run of `devops k8s deploy-stack` SHALL list, in `details.helm_commands` after the repository commands, one `helm upgrade --install` command for each release of the selected stacks, in the order of the real run. Each command SHALL carry the release name, the chart, the version, the namespace and `--values <file>` for each values file, in the order of the Application. It SHALL carry `--kube-context <context>` when a context is set, and `--wait --timeout <timeout>` when the run waits.

#### Scenario: The logging stack dry run lists the loki upgrade with chart and version
- **WHEN** `devops k8s deploy-stack --stack logging --k8s-dir k8s --context ctx-example --dry-run` runs in a checkout of devops-cli
- **THEN** the last entry of `details.helm_commands` is `["helm", "upgrade", "--install", "--take-ownership", "loki", "grafana-community/loki", "--version", <the targetRevision of Application loki>, "--namespace", "logging", "--values", "k8s/logging/loki-values.yaml", "--kube-context", "ctx-example", "--wait", "--timeout", "10m"]`

#### Scenario: A dry run with no wait lists no wait flag
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --no-wait --dry-run` runs
- **THEN** the last entry of `details.helm_commands` holds neither `--wait` nor `--timeout`

#### Scenario: The prometheus release gets the environment values, then the product alert rules
- **WHEN** `devops k8s deploy-stack --stack infra --k8s-dir <tmp>/env --dry-run` runs on a tree whose Applications pin each chart of stack `infra`, and the chart source of Application `prometheus` lists `$values/env/monitoring/prometheus-values.yaml` and then `$values/env/devops/monitoring/prometheus-rules-values.yaml`
- **THEN** the `helm upgrade` command of release `prometheus` names `<tmp>/env/monitoring/prometheus-values.yaml`, then `<tmp>/env/devops/monitoring/prometheus-rules-values.yaml`, each after `--values`, and the version that its Application pins

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
- **WHEN** a person runs `uv run devops k8s deploy-stack --stack infra --dry-run`
- **THEN** `helm_releases` lists `cloudnative-pg` and `cert-manager` before `plugin-barman-cloud`, and the Helm command of `plugin-barman-cloud` names namespace `cnpg-system`, the namespace of `cloudnative-pg`
- **AND** the dry run of each other stack lists none of the three releases

#### Scenario: Argo CD syncs the plugin after cert-manager
- **WHEN** Argo CD syncs Application `cluster`, and a person runs `kubectl -n argocd get applications cert-manager plugin-barman-cloud`
- **THEN** both Applications are `Synced` and `Healthy`, and the sync of `plugin-barman-cloud` reports no missing cert-manager resource

### Requirement: deploy-stack gives each chart the values files of its Application
Each Helm release that `devops k8s deploy-stack` installs SHALL take its values files from `helm.valueFiles` of the chart source of the Argo CD Application of the same name in the environment tree, in their order, so a cluster without Argo CD installs each chart with the values that Argo CD syncs. The code SHALL hold no list of values files. A values file `$<ref>/<path>` SHALL name the file `<path>` of the source of the Application whose `ref` is `<ref>`.

#### Scenario: A values template of another repository comes before the environment values
- **WHEN** the chart source of Application `loki` of a tree `<tmp>/env` lists `$infra/helm/loki/values.yaml` and then `$values/env/logging/loki-values.yaml`, its `infra` source is `https://example.com/infra.git` at `v1.0.0`, its `values` source is the repository of the tree, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the `helm upgrade --install` command of release `loki` gives `--values <fetch>/helm/loki/values.yaml` and then `--values <tmp>/env/logging/loki-values.yaml`

### Requirement: deploy-stack fetches the values files of another repository before it touches the cluster
`devops k8s deploy-stack` SHALL read a values file of the source that is the `origin` of the checkout of the tree in that checkout. It SHALL fetch the repository of another source at its `targetRevision` before the deploy touches the cluster, and SHALL keep the fetched files until the Helm releases are installed. A dry run SHALL fetch nothing and SHALL list, in `details.source_fetches`, each git command of the fetches that the real run makes.

#### Scenario: The dry run lists the fetch of the values template
- **WHEN** the Application `loki` of a tree `<tmp>/env` names `$infra/helm/loki/values.yaml`, its `infra` source is `https://example.com/infra.git` at `v1.0.0`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** `details.source_fetches` gives the `git init` of `<fetch>`, the shallow `git fetch` of `https://example.com/infra` at `v1.0.0` and the checkout of `FETCH_HEAD`, and the command starts no git fetch

### Requirement: deploy-stack applies the builds of the path sources of the Applications of each stack
`devops k8s deploy-stack` SHALL build each path source of each Argo CD Application that `APPLICATIONS_BY_STACK` names for a selected stack, with Kustomize. A source of the `origin` of the checkout of the tree SHALL read the checkout, and a source of another repository SHALL be fetched at its `targetRevision` before the deploy touches the cluster. The deploy SHALL apply each build that holds an object with `kubectl apply -f -` before the charts.

#### Scenario: The build of a path source with a component is applied before the charts
- **WHEN** the tree `<tmp>/env` holds the Application `logging` with the path source `env/logging`, whose kustomization takes the local component `env/components/perimeter`, `kubectl kustomize` of `<tmp>/env/logging` gives two NetworkPolicies, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --no-push-secrets` runs on a cluster without Argo CD
- **THEN** the deploy starts `kubectl apply -f -` with the build as input before the `helm upgrade` of release `loki`

### Requirement: deploy-stack stops when the cluster refuses a build
When `kubectl apply -f -` of a build exits with an error, `devops k8s deploy-stack` SHALL exit 1 with the reason of kubectl, and SHALL install no chart.

#### Scenario: A refused build stops the deploy before the charts
- **WHEN** the tree `<tmp>/env` holds the Application `logging` of the scenario above, kubectl refuses `kubectl apply -f -` with `admission denied`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --no-push-secrets` runs on a cluster without Argo CD
- **THEN** the command exits 1, prints `admission denied`, and starts no `helm upgrade`

### Requirement: teardown-stack deletes the builds of the path sources
`devops k8s teardown-stack` SHALL build the same path sources as `deploy-stack`, and SHALL delete each build that holds an object with `kubectl delete -f - --ignore-not-found`, in the reverse order of the deploy, before the manifest paths and the Helm uninstalls. When kubectl refuses a delete, the teardown SHALL print the reason and go on. When a build fails, the teardown SHALL exit 1 with the reason before it deletes an object or uninstalls a chart.

#### Scenario: The teardown deletes the build before the chart
- **WHEN** the tree `<tmp>/env` holds the Application `logging` of the scenario above, and `devops k8s teardown-stack --stack logging --k8s-dir <tmp>/env` runs on a cluster without Argo CD
- **THEN** the teardown starts `kubectl delete -f - --ignore-not-found` with the build as input before the `helm uninstall` of release `loki`

#### Scenario: A failed build stops the teardown
- **WHEN** the tree `<tmp>/env` holds the Application `logging` of the scenario above, `kubectl kustomize` of `<tmp>/env/logging` exits 1 with `missing resource`, and `devops k8s teardown-stack --stack logging --k8s-dir <tmp>/env` runs on a cluster without Argo CD
- **THEN** the command exits 1, prints `missing resource`, and starts no `kubectl delete` and no `helm` command

### Requirement: deploy-stack stops on an Application that the tree does not hold
When the tree holds no Application of a name that `APPLICATIONS_BY_STACK` gives for a selected stack, `devops k8s deploy-stack` and `devops k8s teardown-stack` SHALL exit 1 and name the Application before they touch the cluster.

#### Scenario: A tree with no Application of the table
- **WHEN** the tree `<tmp>/env` holds the Application `loki` and no Application `logging`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the command exits 1 and names the Application `logging`

### Requirement: The deploy-stack dry run lists the objects of each build
The dry run of `devops k8s deploy-stack` SHALL build each path source of the checkout as a local read. It SHALL list in `details.path_sources`, in the order of the deploy, the key `<application>: <path>` of each build with its objects: `<kind> <namespace>/<name>`, or `<kind> <name>` for an object of the cluster scope. The dry run of `devops k8s teardown-stack` SHALL list the same entries in `details.path_source_deletes`, in the order of the deletes.

#### Scenario: The dry run lists the objects of the build of a component
- **WHEN** the tree `<tmp>/env` holds the Application `logging` with the path source `env/logging`, `kubectl kustomize` of `<tmp>/env/logging` gives the NetworkPolicy `logging/loki-perimeter` and the NetworkPolicy `logging/default-deny` of the component, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** `details.path_sources` is the one entry `logging: env/logging` with `NetworkPolicy logging/loki-perimeter` and `NetworkPolicy logging/default-deny`, and the command starts `kubectl kustomize` only as a local read

#### Scenario: The teardown dry run lists the builds in the order of the deletes
- **WHEN** the Application `logging` of the tree `<tmp>/env` has the path sources `env/logging` and `env/extra`, and `devops k8s deploy-stack` and `devops k8s teardown-stack` run with `--stack logging --k8s-dir <tmp>/env --dry-run`
- **THEN** `details.path_sources` gives `logging: env/logging` and then `logging: env/extra`, and `details.path_source_deletes` gives `logging: env/extra` and then `logging: env/logging`

### Requirement: The deploy-stack dry run fetches no path source of another repository
For a path source of another repository, the dry run of `devops k8s deploy-stack` SHALL fetch nothing and build nothing. It SHALL list the fetch in `details.source_fetches`, and SHALL give `null` as the objects of the source in `details.path_sources`.

#### Scenario: The dry run lists the fetch of a path source
- **WHEN** the path source of the Application `logging` of the tree `<tmp>/env` is `k8s/logging` of `https://example.com/infra.git` at `v1.0.0`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the entry of `details.path_sources` gives `null` as its objects, `details.source_fetches` lists the fetch of `https://example.com/infra` at `v1.0.0`, and the command starts no git fetch and no `kubectl kustomize`

### Requirement: The stack dry runs build no folder that reaches a remote target
The dry runs of `devops k8s deploy-stack` and `devops k8s teardown-stack` SHALL NOT start `kubectl kustomize` on a path source whose kustomization, or the kustomization of a local folder that it reaches, names a remote target: an http or https URL, or a git repository that Kustomize clones. They SHALL give `null` as the objects of such a build, and SHALL list its remote targets in `details.kustomize_fetches` under the key of the build. The real run SHALL build the folder as before.

#### Scenario: A local base that names a remote base
- **WHEN** the path source `env/logging` of the Application `logging` of the tree `<tmp>/env` takes the local base `../bases/loki`, whose kustomization names `https://example.com/infra.git//k8s/bases/loki?ref=v0.1.0`, and `devops k8s deploy-stack` and `devops k8s teardown-stack` run with `--stack logging --k8s-dir <tmp>/env --dry-run`
- **THEN** both commands exit 0, start no `kubectl kustomize`, give `null` as the objects of `logging: env/logging`, and list the remote base under `logging: env/logging` in `details.kustomize_fetches`

#### Scenario: A folder with only local bases and components
- **WHEN** the path source `env/logging` takes only the local component `../components/perimeter`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the command builds the folder with `kubectl kustomize` as a local read, and `details.kustomize_fetches` is empty
