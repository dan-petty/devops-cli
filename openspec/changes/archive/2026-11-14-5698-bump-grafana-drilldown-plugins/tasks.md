# Tasks

## 1. Behavior

- [x] 1.1 Assert in tests that all four Drilldown plugins are pinned to version 3.2.0
  - Verification: `$ uv run pytest tests/commands/k8s/test_k8s_monitoring_integration.py -k test_grafana_pins_each_drilldown_app_at_its_release_for_grafana_13 -n 0`
- [x] 1.2 Update Drilldown plugin pins to 3.2.0 in k8s/monitoring/grafana-values.yaml
  - Verification: `$ uv run pytest tests/commands/k8s/test_k8s_monitoring_integration.py -k test_grafana_pins_each_drilldown_app_at_its_release_for_grafana_13 -n 0`
