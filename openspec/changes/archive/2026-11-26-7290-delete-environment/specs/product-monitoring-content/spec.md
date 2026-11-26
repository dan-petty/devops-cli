## ADDED Requirements

### Requirement: Each row of the Alerting table fits its header
Each row of the Alerting table of `k8s/README.md` SHALL have no more cells than its header.

#### Scenario: A row with one cell too many
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` reads a row that holds more cells than the header
- **THEN** the check fails and names the row

### Requirement: Each product SLO has one Sloth spec
The product SHALL hold one Sloth `prometheus/v1` spec under `k8s/devops/monitoring/slos/` for each of the four SLOs, and each spec SHALL name its service, the objective of its SLO and the 28-day window.

#### Scenario: Each SLO has one spec
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command exits 0, and the four specs of the folder load and render

### Requirement: The k8s row builds the product dashboards
The `k8s` row SHALL build `k8s/devops/dashboards`, and SHALL refuse a build whose ConfigMap does not hold each JSON file of the folder, and dashboards that the dashboard linter refuses together, such as two with one uid.

#### Scenario: The committed folder
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the checks of the dashboards folder report a pass

#### Scenario: A dashboard file that the kustomization does not list
- **WHEN** `uv run devops ci --check --only k8s` runs on a folder that holds a JSON file that its kustomization does not list
- **THEN** it exits non-zero and names the check of the folder

## MODIFIED Requirements

### Requirement: The product dashboards have their own generator
`k8s/devops/dashboards/kustomization.yaml` SHALL generate the ConfigMap `grafana-devops-cli-dashboards` in namespace `monitoring` from each dashboard of the folder, with no content hash, with the label `grafana_dashboard: "1"` and with the annotation `grafana_folder: "dan-petty/devops-cli"`. The environment repository applies that folder.

#### Scenario: The generators of the dashboards
- **WHEN** `kubectl kustomize k8s/devops/dashboards` renders the folder
- **THEN** the output is the one ConfigMap `grafana-devops-cli-dashboards`, with a key for each JSON file of the folder, its namespace, label and annotation

### Requirement: Application devops does not own the product dashboards
`k8s/devops/kustomization.yaml` SHALL NOT reach `k8s/devops/dashboards`, because then two Applications own one ConfigMap and sync it in turn.

#### Scenario: Application devops leaves the ConfigMap to Application monitoring
- **WHEN** `kubectl kustomize k8s/devops` renders the product base
- **THEN** the render holds no ConfigMap `grafana-devops-cli-dashboards`

### Requirement: The product alert rules have their own values file
The product rule file `k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold, under `serverFiles.devops_cli_alerting_rules.yml`, each rule group that selects a `devops_cli_` series and the four `slo-` groups of this change.

#### Scenario: The product file holds the groups that watch a devops_cli series
- **WHEN** `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs
- **THEN** the command exits 0, the product file holds each group that selects a `devops_cli_` series and the four `slo-` groups

## REMOVED Requirements

### Requirement: The server loads the product rule file
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: One Sloth spec for each SLO of the product
**Reason**: The catalog data is `catalog.toml` of the environment tree, so the `k8s` row compares no spec with it (#7290).
**Migration**: See `Each product SLO has one Sloth spec`. `devops k8s catalog` still refuses a spec whose service the catalog of its tree does not hold.
