# Tasks

## 1. Behavior

- [x] 1.1 Update tests to assert stat, state-timeline, and status-history panels and rows
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_k8s_monitoring_dashboards.py -k test_system_topology`
- [x] 1.2 Implement stat, state-timeline, and status-history panels in system-topology.json
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_k8s_monitoring_dashboards.py`

## 2. Documents

- [x] 2.1 Update living spec and change specification in OpenSpec
  - Verification: `$ uv run devops openspec check`
