## MODIFIED Requirements

### Requirement: The pod renders its settings at start
The SearXNG Deployment SHALL render `/etc/searxng/settings.yml` at pod start from the `searxng-settings` ConfigMap and the `password` key of Secret `searxng-metrics-auth` into the `settings-rendered` `emptyDir`, and SHALL mount that rendered file in place of the ConfigMap file.

#### Scenario: The rendered settings hold the password of the Secret
- **WHEN** `uv run devops ci --check --only k8s` runs `render-settings` with a password that holds `&`, `\` and `|`
- **THEN** the init container exits 0, the rendered `general.open_metrics` is that password, and it logs nothing

#### Scenario: The live check answers after the rollout
- **WHEN** `uv run devops k8s searxng-check` runs after the rollout of `k8s/devops/searxng/deployment.yaml`
- **THEN** the check exits 0 and its `general` row holds at least one hit

## ADDED Requirements

### Requirement: The pod starts without the metrics Secret
The reference of the init container `render-settings` to Secret `searxng-metrics-auth` SHALL be optional. When the Secret or its key `password` is missing, `render-settings` SHALL write an empty `general.open_metrics`, which turns the OpenMetrics endpoint off, SHALL log one line that names Secret `devops/searxng-metrics-auth`, and SHALL exit 0.

#### Scenario: The pod starts without the metrics Secret
- **WHEN** `uv run devops ci --check --only k8s` runs `render-settings` with no Secret `searxng-metrics-auth`
- **THEN** the init container starts and exits 0, the rendered settings hold an empty `general.open_metrics`, and its log is one line that names `devops/searxng-metrics-auth`
