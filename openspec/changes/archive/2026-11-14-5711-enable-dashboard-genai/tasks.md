# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for the dashgpt feature toggle in grafana-values.yaml
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py -k test_grafana_enables_dashgpt_feature_toggle`
- [x] 1.2 Enable dashgpt in grafana.ini in k8s/monitoring/grafana-values.yaml
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py`

## 2. Documents

- [x] 2.1 Update Grafana LLM Plugin section in k8s/README.md
  - Verification: `$ uv run devops ci docs`
