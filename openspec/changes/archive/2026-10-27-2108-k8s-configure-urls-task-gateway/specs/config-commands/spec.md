# Spec Delta

## MODIFIED Requirements

### Requirement: Each command that saves the settings writes only its own keys
Each command that saves the settings SHALL write only the keys that it changes. The scenario of each command names its keys.

#### Scenario: devops ai runs connect
- **WHEN** `devops ai runs connect` finds the run index and the index answers
- **THEN** the one config write names `runs.index_url` alone

#### Scenario: devops k8s configure-urls
- **WHEN** `devops k8s configure-urls --stack infra` detects the ArgoCD, Grafana, Prometheus, Pyroscope and Tempo services
- **THEN** the one config write names `argocd.url`, `grafana.url`, `prometheus.url`, `pyroscope.url`, `telemetry.endpoint` and `tempo.url`

#### Scenario: devops k8s configure-urls task gateway URLs
- **WHEN** `devops k8s configure-urls` changes only task gateway URLs
- **THEN** the one config write names each changed `ai.tasks.<task>.api_base_url` key, and the report displays the changed keys

#### Scenario: devops k8s switch-context
- **WHEN** the config file holds `k8s.context: default`, and `devops k8s switch-context production-cluster` runs
- **THEN** the file holds `k8s.context: production-cluster` and nothing more

#### Scenario: devops ai config
- **WHEN** `devops ai config --task chat --provider gateway --model devops-coder` runs
- **THEN** the one config write names `ai.tasks.chat.model` and `ai.tasks.chat.provider`

#### Scenario: devops telemetry connect
- **WHEN** the config file holds `telemetry.enabled: false`, and `devops telemetry connect` finds a collector that answers
- **THEN** the file holds `telemetry.enabled: true` and the `telemetry.endpoint` of the collector, and nothing more

#### Scenario: devops ai gateway connect
- **WHEN** the config file holds `ai.allow_private_network: false`, and `devops ai gateway connect` finds a gateway that answers
- **THEN** the one config write names `ai.allow_private_network` and `ai.gateway_url`

#### Scenario: devops config set
- **WHEN** `devops config set github.default_org first-org` runs
- **THEN** the config file gets `github.default_org: first-org` after its other lines, and the audit record names `github.default_org` alone

#### Scenario: devops config init
- **WHEN** the answers to `devops config init` name a new default org and a new repos directory, and skip the other questions
- **THEN** the one config write names `github.default_org` and `repos.base_dir`
