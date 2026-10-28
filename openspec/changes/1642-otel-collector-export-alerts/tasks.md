# Tasks

## 1. The collector's export health alerts

- [x] Add failing tests: the two rules pinned with their severity, wait and labels; each series that they select is a family of the collector capture; the promtool unit tests of the group; the baseline rule set and the served series
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [x] Capture the collector's `/metrics` again at contrib 0.161.0, and add the three `send_failed` families under `from_source` with their source
  - Verification: `uv run devops ci test tests/test_stack_dashboards.py tests/test_k8s_monitoring_alerting.py`
- [x] Add the `otel-collector` group with `OtelCollectorExportFailing` and `OtelCollectorExportQueueFull`
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [x] List both alerts in the Alerting table of `k8s/README.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1642-otel-collector-export-alerts`
- Pending a person: after Argo CD syncs the merge, read the two rules in Grafana's Alerting view. Each stays Normal while Tempo, Prometheus and Loki accept the collector's data.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
