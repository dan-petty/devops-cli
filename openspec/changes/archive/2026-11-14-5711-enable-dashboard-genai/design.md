# Design: #5711

## Context
Grafana 13 supports AI assistance across dashboards and query editors through `grafana-llm-app`. Dashboard features such as AI title and description generation are guarded by the `dashgpt` feature toggle in Grafana's core configuration.

## Decisions

### 1. Enable dashgpt in grafana.ini
- Set `feature_toggles.enable = dashgpt` in `k8s/monitoring/grafana-values.yaml` under `grafana.ini`.
- This activates dashboard AI actions, including generating panel descriptions and explanations.

## Rejected Alternatives
- Leave feature toggle disabled: Rejected because operators would not have access to dashboard generative AI features.
