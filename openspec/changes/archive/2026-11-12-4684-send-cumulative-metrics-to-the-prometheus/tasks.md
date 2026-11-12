# Tasks

## 1. Behavior: the metrics export path

- [x] 1.1 Change the tests of the export path: the collector sends metrics only to an `otlp_http` exporter at `/api/v1/otlp/v1/metrics` and sets the `cluster` attribute, the Prometheus server runs the OTLP receiver with the zero sample feature and the translation strategy, and `max_stale` stays at 1h
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py tests/telemetry/test_telemetry_instruments.py`
- [x] 1.2 Replace `prometheus_remote_write` with `otlp_http/prometheus` and add `transform/cluster` in `k8s/otel/values.yaml`; add `web.enable-otlp-receiver` and `server.otlp` in `k8s/monitoring/prometheus-values.yaml`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py tests/telemetry/test_telemetry_instruments.py`

## 2. Manifests: the collector dashboard and its fixture

- [x] 2.1 Add the row "Processors" and the panel "Delta Points Dropped by deltatocumulative" to `otel-collector.json`; remove the remote-write exporter families from `tests/fixtures/metrics/otel-collector.yaml` and give the metric point families the endpoint labels of `otlp_http`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_stack_dashboards.py tests/grafana/test_grafana_dashboards.py tests/prometheus/test_k8s_monitoring_alerting.py`

## 3. Documents

- [x] 3.1 Name the OTLP receiver path in `docs/TELEMETRY.md` and in its text in `src/devops_cli/docs/generator.py`
  - Verification: `! git grep -n remote_write_version -- docs src k8s tests`

- Pending a person: 24 h after Argo CD syncs the collector and the Prometheus server, `count(min_over_time(devops_cli_github_requests_total[24h]) == 0)` is more than 0, and for job `devops-cli-job` `sum(increase(devops_cli_command_total[24h]))` is within 2 % of `sum(max_over_time(devops_cli_command_total[24h]))`. A test cannot reach the cluster.
- Pending a person: the panel "Delta Points Dropped by deltatocumulative" stays under 0.5 % over 24 h, and `resets(devops_cli_github_throttle_wait_seconds[24h])` shows no reset outside a pod or collector start.
- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
