# Task: Direct Prometheus Remote Write for OTel Metrics and Out-of-Order TSDB Window (#1132)

**Issue**: [#1132](https://github.com/dan-petty/devops-cli/issues/1132)
**Scope**: scope/telemetry
**Feasibility**: Confirmed through Prometheus and OpenTelemetry Collector Helm chart specifications and manifests in `k8s/monitoring/` and `k8s/otel/`. The Prometheus server enables remote-write receiving (`web.enable-remote-write-receiver`) and supports the `tsdb.out_of_order_time_window` setting. Direct remote-write from OTel collector to `prometheus-server.monitoring.svc.cluster.local:9090/api/v1/write` removes the two-hop path through Alloy that previously dropped entire batches on late samples. All manifest invariants and values configurations are validated offline by `tests/test_k8s_monitoring_integration.py`.

## Description

- [x] Set `server.tsdb.out_of_order_time_window: 10m` in `k8s/monitoring/prometheus-values.yaml` to prevent batch rollbacks on late samples.
- [x] Repoint OpenTelemetry collector remote write exporter to `prometheus_remote_write` targeting direct Prometheus server endpoint `http://prometheus-server.monitoring.svc.cluster.local:9090/api/v1/write` with `external_labels.cluster` matching cluster name (`k8s/otel/values.yaml`).
- [x] Disable `prometheusMetricsReceiver` in `k8s/monitoring/k8s-monitoring-values.yaml`.
- [x] Set unused receivers (`jaeger`, `zipkin`, `prometheus`) to `null` and disable unused ports (`jaeger-compact`, `jaeger-thrift`, `jaeger-grpc`, `zipkin`) in `k8s/otel/values.yaml`.
- [x] Set redundant memory limiter percentage parameters (`limit_percentage`, `spike_limit_percentage`) to `null` in favor of MiB limits.
- [x] Remove `debug` exporter from all pipelines and exporter configurations in `k8s/otel/values.yaml`.
- [x] Remove collector `image.tag` override in `k8s/otel/values.yaml` so the collector follows the pinned chart.
- [x] Update integration test `test_otel_collector_remote_writes_to_the_path_alloy_serves` in `tests/test_k8s_monitoring_integration.py` to assert direct remote write, null receivers, disabled ports, and absence of debug exporters.
- Pending a person: verify on a running cluster that Alloy logs show zero batch drop errors and Prometheus receives `devops_cli_command_total` metrics directly.
