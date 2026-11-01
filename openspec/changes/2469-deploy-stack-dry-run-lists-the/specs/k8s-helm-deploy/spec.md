## ADDED Requirements

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
The `helm repo` and `helm upgrade` commands in `details.helm_commands` of a `devops k8s deploy-stack` dry run SHALL be built by the builders that the real run uses, so that the real run starts the same argument lists, in the same order, for the same options on Helm 3.

#### Scenario: The real run starts the commands that the dry run lists
- **WHEN** `devops k8s deploy-stack --stack logging --context ctx-example --no-wait --no-push-secrets` runs against a process double that answers Helm 3.17.0 and a ready cluster, and the same command runs with `--dry-run`
- **THEN** the `helm repo` and `helm upgrade` commands that the process double recorded equal `details.helm_commands` of the dry run

### Requirement: deploy-stack dry run lists the Helm commands as for Helm 3
The dry run of `devops k8s deploy-stack` SHALL NOT run `helm version`. It SHALL list each `helm upgrade --install` command without `--force-conflicts`, the flag that the real run adds on Helm 4 or later.

#### Scenario: The dry run starts no process
- **WHEN** `devops k8s deploy-stack --stack logging --dry-run` runs against a process double
- **THEN** the double records no `helm` command and `details.helm_commands` holds no `--force-conflicts`
