# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for the grafana-llm-app plugin pin
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py -k test_grafana_pins_the_llm_app_at_its_release_for_grafana_13`
- [x] 1.2 Add grafana-llm-app@1.2.0 to plugins in k8s/monitoring/grafana-values.yaml
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py -k test_grafana_pins_the_llm_app_at_its_release_for_grafana_13`

## 2. Documents

- [x] 2.1 Document LLM app plugin configuration in k8s/README.md
  - Verification: `$ uv run devops ci docs`
