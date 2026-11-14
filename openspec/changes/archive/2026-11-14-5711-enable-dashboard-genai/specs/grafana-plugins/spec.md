## ADDED Requirements

### Requirement: Grafana enables the dashgpt feature toggle
The Grafana values SHALL enable the `dashgpt` feature toggle under `grafana.ini.feature_toggles.enable` in `k8s/monitoring/grafana-values.yaml`.

#### Scenario: Feature toggle in Grafana values
- **WHEN** `k8s/monitoring/grafana-values.yaml` is read
- **THEN** `grafana.ini.feature_toggles.enable` contains `dashgpt`
