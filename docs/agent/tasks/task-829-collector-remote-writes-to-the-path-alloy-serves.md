# Task: The Collector Remote-Writes devops-cli Metrics to the Path Alloy Serves (#829)

**Issue**: [#829](https://github.com/dan-petty/devops-cli/issues/829)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/telemetry

## Description
fdd4d0f (#734) moved the OpenTelemetry collector's `prometheusremotewrite` exporter (`k8s/otel/values.yaml`) from the kube-prometheus-stack Prometheus to `k8s-monitoring-alloy-metrics.monitoring.svc.cluster.local:9090`, but kept the Prometheus server's `/api/v1/write` path. k8s-monitoring's `prometheusMetricsReceiver` runs Alloy's `prometheus.receive_http`, which serves only `POST /api/v1/metrics/write`. Alloy answered every write with 404, and the exporter treats a 4xx other than 429 as permanent, so it dropped every devops-cli metric point without a retry, and the devops-cli and AI spend dashboards (#692, #693) stayed empty. fdd4d0f is not in v0.2.23, so this is a regression in v0.2.24, admitted by the owner as a critical fix.

On homelab-k3s, read-only:
- Alloy counted `prometheus_receive_http_request_duration_seconds_count{method="POST",status_code="404"} 245` and `prometheus_forwarded_samples_total{component_id="prometheus.receive_http.default"} 0`.
- A GET to `/api/v1/metrics/write` answers 405, so the route exists.
- The collector that ran Helm revisions 90-95 logged `failed to send WriteRequest ... "status_code": 404`.

The endpoint keeps the route through Alloy, so devops-cli series carry the same cluster external labels and WAL-backed queue as the other metrics. Alloy's onward write to the Prometheus server already succeeds (14,207 responses with code 204).

The `context deadline exceeded` errors the issue first recorded come from a different fault. The live collector, Helm revision 96, runs the v0.2.23 values, which point at the deleted `kube-prometheus-kube-prome-prometheus` Service. That clears when a person redeploys the collector from a branch with this fix (`devops k8s deploy-stack`).

## Acceptance Criteria
- [x] The exporter posts to the path Alloy serves. `test_otel_collector_remote_writes_to_the_path_alloy_serves` (`tests/test_k8s_monitoring_integration.py`) reads `k8s/otel/values.yaml` and `k8s/monitoring/k8s-monitoring-values.yaml`. With `prometheusMetricsReceiver` enabled on `alloy-metrics`, it asserts that the endpoint's host is `k8s-monitoring-alloy-metrics.monitoring.svc.cluster.local`, its port is 9090 and its path is `/api/v1/metrics/write`. Against fdd4d0f's values it failed on the path, `/api/v1/write`.
- [x] The test reads only files in the repository, with no network.
- [x] `uv run devops ci` passes.

After merge, a person checks the homelab once the collector is redeployed: Alloy's POSTs answer 2xx, `otelcol_exporter_send_failed_metric_points{exporter="prometheusremotewrite"}` stays flat, and `devops_cli_command_total` appears in Prometheus.
