# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for system topology dashboard and provisioning
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_k8s_monitoring_dashboards.py -k test_system_topology`
- [x] 1.2 Implement the system-topology.json dashboard and kustomization generator
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_k8s_monitoring_dashboards.py`

## 2. Documents

- [x] 2.1 Update documentation and validate OpenSpec
  - Verification: `$ uv run devops openspec check`
