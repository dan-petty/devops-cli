## MODIFIED Requirements

### Requirement: deploy-stack dry run lists the Helm upgrade commands
The dry run of `devops k8s deploy-stack` SHALL list, in `details.helm_commands` after the repository commands, one `helm upgrade --install` command for each release of the selected stacks, in the order of the real run. Each command SHALL carry the release name, the chart, the version, the namespace and `--values <file>` for each values file, in the order of the Application. It SHALL carry `--kube-context <context>` when a context is set, and `--wait --timeout <timeout>` when the run waits.

#### Scenario: The logging stack dry run lists the loki upgrade with chart and version
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --dry-run` runs
- **THEN** the last entry of `details.helm_commands` is `["helm", "upgrade", "--install", "--take-ownership", "loki", "grafana-community/loki", "--version", <the targetRevision of Application loki>, "--namespace", "logging", "--values", "k8s/logging/loki-values.yaml", "--kube-context", "ctx-example", "--wait", "--timeout", "10m"]`

#### Scenario: A dry run with no wait lists no wait flag
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --no-wait --dry-run` runs
- **THEN** the last entry of `details.helm_commands` holds neither `--wait` nor `--timeout`

#### Scenario: The prometheus release gets the environment values, then the product alert rules
- **WHEN** `devops k8s deploy-stack --stack infra --k8s-dir <tree> --product-dir <base> --dry-run` runs on a tree whose Applications pin each chart of stack `infra`
- **THEN** the `helm upgrade` command of release `prometheus` names `<tree>/monitoring/prometheus-values.yaml`, then `<base>/monitoring/prometheus-rules-values.yaml`, each after `--values`, and the version that its Application pins
