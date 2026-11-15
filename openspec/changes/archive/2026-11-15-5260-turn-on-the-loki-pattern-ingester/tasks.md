# Tasks

## 1. Enable the pattern ingester

Reads: `k8s/logging/loki-values.yaml`.

Changes: `k8s/logging/loki-values.yaml`, `tests/k8s/test_loki_pattern_ingester.py`.

- [x] 1.1 Write the render test and watch it fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_loki_pattern_ingester.py`
- [x] 1.2 Add the value.
  - Verification: `$ uv run devops ci test tests/k8s/test_loki_pattern_ingester.py`

## Workflow follow-up

- Pending a person: sync the `logging` Application, read `pattern_ingester.enabled` from the Loki `/config`, and run `query_loki_patterns` for `{namespace="devops"}` over the last hour.
