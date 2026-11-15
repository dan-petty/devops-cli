# Tasks

## 1. Behavior

- [x] 1.1 Add table tests for `phase(item)`, phase age, and stall criteria in `tests/roadmap/test_roadmap_phase.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_phase.py`
- [x] 1.2 Implement `phase(item)`, `phase_age(item, now)`, and `is_stalled(...)` in `src/devops_cli/roadmap/phase.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_phase.py`
- [x] 1.3 Add tests for `ROADMAP_ITEMS` and `ROADMAP_STALLED_ITEMS` gauges and zero-emission on empty phases in `tests/github/test_github_metrics.py`
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py`
- [x] 1.4 Update telemetry instruments in `src/devops_cli/telemetry/instruments.py` and emissions in `src/devops_cli/github/metrics.py`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py tests/github/test_github_metrics.py`
- [x] 1.5 Update `RoadmapServiceItemStuck` rule in `k8s/devops/monitoring/prometheus-rules-values.yaml` and promtool unit tests in `tests/fixtures/prometheus_rules/roadmap_service_items_tests.yaml`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 1.6 Update dashboard panel in `k8s/devops/dashboards/project-metrics.json`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py`
- [x] 1.7 Update `devops roadmap explain` to print phase and phase age
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py`

## 2. Documents

- [x] 2.1 Update documentation and regenerate command docs
  - Verification: `$ uv run devops docs generate && uv run devops ci docs`
