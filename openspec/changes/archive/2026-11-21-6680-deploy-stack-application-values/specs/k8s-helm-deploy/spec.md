## ADDED Requirements

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

## MODIFIED Requirements

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
