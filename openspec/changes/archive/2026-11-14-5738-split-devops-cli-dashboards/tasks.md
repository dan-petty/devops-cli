# Tasks

## 1. Behavior

- [x] 1.1 Update tests for dashboard provisioning, telemetry instruments, and queries
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_k8s_monitoring_dashboards.py`
- [x] 1.2 Implement partitioned dashboards devops-cli.json, roadmap-service-telemetry.json, and devops-ai-rag.json
  - Verification: `$ uv run devops grafana dashboards lint`
- [x] 1.3 Add top header links and sidecar folder annotations
  - Verification: `$ uv run pytest -n 0 tests/grafana/test_grafana_dashboards.py`

## 2. Documents

- [x] 2.1 Update living specifications and change records in OpenSpec
  - Verification: `$ uv run devops openspec check`
