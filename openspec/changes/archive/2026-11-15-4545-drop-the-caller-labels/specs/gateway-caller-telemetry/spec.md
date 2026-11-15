## ADDED Requirements

### Requirement: The gateway drops the caller address and user agent
The `http` endpoint of the LLM gateway ServiceMonitor SHALL hold one `metricRelabelings` entry with `action: labeldrop` for each of `client_ip` and `user_agent`, and SHALL keep its port, path and interval.

#### Scenario: The endpoint holds one labeldrop rule for each label
- **WHEN** a check reads `k8s/llm/gateway/servicemonitor.yaml` and collects the `regex` of every `metricRelabelings` entry with `action: labeldrop` on the `http` endpoint
- **THEN** the collected values are exactly `client_ip` and `user_agent`, and the endpoint still names port `http`, path `/metrics/` and interval `15s`

### Requirement: No query reads the dropped labels
Every query of `k8s/devops/dashboards/ai-spend.json` and `k8s/monitoring/dashboards/llm-stack.json` and every alert expression of `k8s/monitoring/prometheus-values.yaml` that reads a `litellm_` series MUST NOT group by or filter on `client_ip` or `user_agent`.

#### Scenario: The dashboards and the alerts ignore the labels
- **WHEN** a check reads the target expressions of both dashboards and the `serverFiles.alerting_rules.yml` expressions of the Prometheus values
- **THEN** no expression names `client_ip` or `user_agent`

### Requirement: The manifest check runs in the k8s row
The labeldrop check SHALL run in the `k8s` row of `devops ci`, which the Static Analysis check runs.

#### Scenario: The k8s row reports the check
- **WHEN** the `k8s` row runs the `check_*` functions under `tests/gate/k8s_checks/`
- **THEN** the three gateway label checks report a pass
