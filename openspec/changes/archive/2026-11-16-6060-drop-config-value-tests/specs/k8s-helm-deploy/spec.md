## MODIFIED Requirements

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

### Requirement: deploy-stack dry run lists the Helm upgrade commands
The dry run of `devops k8s deploy-stack` SHALL list, in `details.helm_commands` after the repository commands, one `helm upgrade --install` command for each release of the selected stacks, in the order of the real run. Each command SHALL carry the release name, the chart, the version, the namespace and `--values <file>` for each values file, in the order of the Application. It SHALL carry `--kube-context <context>` when a context is set, and `--wait --timeout <timeout>` when the run waits.

#### Scenario: The logging stack dry run lists the loki upgrade with chart and version
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --dry-run` runs
- **THEN** the last entry of `details.helm_commands` is `["helm", "upgrade", "--install", "--take-ownership", "loki", "grafana-community/loki", "--version", <the targetRevision of Application loki>, "--namespace", "logging", "--values", "k8s/logging/loki-values.yaml", "--kube-context", "ctx-example", "--wait", "--timeout", "10m"]`

#### Scenario: A dry run with no wait lists no wait flag
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --no-wait --dry-run` runs
- **THEN** the last entry of `details.helm_commands` holds neither `--wait` nor `--timeout`

#### Scenario: The prometheus release gets the environment values, then the product alert rules
- **WHEN** `devops k8s deploy-stack --stack infra --k8s-dir k8s --dry-run` runs
- **THEN** the `helm upgrade` command of release `prometheus` names `k8s/monitoring/prometheus-values.yaml`, then `k8s/devops/monitoring/prometheus-rules-values.yaml`, each after `--values`
- **AND** the `valueFiles` of each Argo CD Application of a chart are the values files of its release, in the same order
