## ADDED Requirements

### Requirement: deploy-stack installs the store with stack infra
`devops k8s deploy-stack --stack infra` SHALL add the chart repository `seaweedfs-operator`, SHALL install release `seaweedfs-operator` into namespace `object-store` after release `cert-manager`, and SHALL apply `object-store` after the charts. No other stack SHALL list the release.

#### Scenario: The stack tables
- **WHEN** a test reads `HELM_REPOS_BY_STACK`, `HELM_RELEASES_BY_STACK` and `POST_HELM_BY_STACK`
- **THEN** stack `infra` holds the repository, the release in `object-store` after `cert-manager`, and the post-Helm path `object-store`, and no other stack holds the release

### Requirement: deploy-stack installs Loki from the open-source chart
The `logging` stack of `devops k8s deploy-stack` SHALL add the repository `https://grafana-community.github.io/helm-charts` as `grafana-community`, and SHALL install chart `grafana-community/loki` into namespace `logging` at the version that Application `loki` of the environment tree pins.

#### Scenario: A dry run of the logging stack
- **WHEN** `devops k8s deploy-stack --stack logging --k8s-dir <tree> --dry-run` runs on a fixture tree
- **THEN** its `helm_commands` add the repository `grafana-community` and install `grafana-community/loki` into namespace `logging` with the `targetRevision` of Application `loki`

## MODIFIED Requirements

### Requirement: deploy-stack deploys the chat stack
The stack `chat` SHALL install Helm release `mattermost-operator`, and apply post-Helm kustomization `mattermost` of the environment tree after the Helm releases complete. The CloudNativePG operator that the `Cluster` of that kustomization needs SHALL be a release of stack `infra`.

#### Scenario: deploy-stack installs chat releases and post-helm kustomization
- **WHEN** a person runs `uv run devops k8s deploy-stack --stack chat --dry-run`
- **THEN** `helm_releases` is `mattermost-operator` with no `cloudnative-pg`, `post_helm` is the kustomization `mattermost` of the tree, and the command makes no request

### Requirement: deploy-stack installs the CloudNativePG operator with stack infra and applies the gateway database after the Helm releases
The stack `infra` SHALL install Helm release `cloudnative-pg` after `prometheus-operator-crds`. The stack `llm` SHALL apply `llm/gateway-db.yaml` of the environment tree as a post-Helm path, so the CloudNativePG CRD exists when the `Cluster` is applied. No other stack SHALL list the release.

#### Scenario: The operator has one stack and the database follows the Helm releases
- **WHEN** a test reads the stack tables of deploy-stack
- **THEN** `cloudnative-pg` is a release of stack `infra` and of no stack that holds a CloudNativePG `Cluster`, `llm/gateway-db.yaml` is a post-Helm path of stack `llm`

### Requirement: deploy-stack dry run lists the Helm upgrade commands
The dry run of `devops k8s deploy-stack` SHALL list, in `details.helm_commands` after the repository commands, one `helm upgrade --install` command for each release of the selected stacks, in the order of the real run. Each command SHALL carry the release name, the chart, the version, the namespace and `--values <file>` for each values file, in the order of the Application. It SHALL carry `--kube-context <context>` when a context is set, and `--wait --timeout <timeout>` when the run waits.

#### Scenario: The logging stack dry run lists the loki upgrade with chart and version
- **WHEN** `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --context ctx-example --dry-run` runs on a fixture tree
- **THEN** the last entry of `details.helm_commands` is `["helm", "upgrade", "--install", "--take-ownership", "loki", "grafana-community/loki", "--version", <the targetRevision of Application loki>, "--namespace", "logging", "--values", "<tmp>/env/logging/loki-values.yaml", "--kube-context", "ctx-example", "--wait", "--timeout", "10m"]`

#### Scenario: A dry run with no wait lists no wait flag
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --no-wait --dry-run` runs
- **THEN** the last entry of `details.helm_commands` holds neither `--wait` nor `--timeout`

#### Scenario: The prometheus release gets the environment values, then the product alert rules
- **WHEN** `devops k8s deploy-stack --stack infra --k8s-dir <tmp>/env --dry-run` runs on a tree whose Applications pin each chart of stack `infra`, and the chart source of Application `prometheus` lists `$values/env/monitoring/prometheus-values.yaml` and then `$values/env/devops/monitoring/prometheus-rules-values.yaml`
- **THEN** the `helm upgrade` command of release `prometheus` names `<tmp>/env/monitoring/prometheus-values.yaml`, then `<tmp>/env/devops/monitoring/prometheus-rules-values.yaml`, each after `--values`, and the version that its Application pins
