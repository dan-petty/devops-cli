# Tasks

## 1. Make the Grafana token optional

Reads: `k8s/monitoring/grafana-values.yaml`, `src/devops_cli/k8s/cluster_secrets.py`.

Changes: `k8s/monitoring/grafana-values.yaml`, `src/devops_cli/k8s/cluster_secrets.py`, `k8s/README.md`, `tests/k8s/test_grafana_renderer_optional.py`, `tests/support/helm.py`.

- [x] 1.1 Write the rendered-chart test and the list test, and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_grafana_renderer_optional.py`
- [x] 1.2 Add the optional entry, the list and the README rule.
  - Verification: `$ uv run python -m tests.gate.k8s`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
