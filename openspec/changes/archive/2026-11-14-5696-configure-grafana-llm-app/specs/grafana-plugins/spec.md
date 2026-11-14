## ADDED Requirements

### Requirement: Grafana preinstalls the LLM app plugin
The Grafana values SHALL include `grafana-llm-app` pinned at release 1.2.0 in the chart `plugins` value as `grafana-llm-app@1.2.0`. The 1.2.0 release is compatible with Grafana 13 (`>=13.0.0-0`).

#### Scenario: The LLM app plugin has a pin
- **WHEN** the Grafana values are read
- **THEN** the `plugins` value contains `grafana-llm-app@1.2.0`
