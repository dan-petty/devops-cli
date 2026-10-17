# Task 792: SDK MeterProvider Delta Aggregation, Exponential Histograms & Prometheus Client Exposition

**Issue**: [#792](https://github.com/dan-petty/devops-cli/issues/792)
**Status**: Done
**Milestone**: `v0.2.36`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/telemetry`, `priority/p2-medium`
**Feasibility**: Verified that `opentelemetry-sdk` 1.38.0 (`MeterProvider`, `InMemoryMetricReader`, `AggregationTemporality.DELTA`, `View`, and `ExponentialBucketHistogramAggregation`) and `prometheus-client` 0.26.0 (`CollectorRegistry`, `Counter`, `Gauge`, `Histogram`, `GaugeMetricFamily`, `CounterMetricFamily`, `generate_latest`, `CONTENT_TYPE_LATEST`, and `text_string_to_metric_families`) satisfy all metric aggregation, exposition, and parsing requirements while keeping `opentelemetry.sdk` lazily loaded outside `--help`.

---

## 1. Description & Objectives

Replace per-point OTLP metric JSON construction and worker-pool HTTP dispatch in `OTelTelemetryClient` with an OpenTelemetry SDK `MeterProvider` configured for `DELTA` aggregation temporality and `ExponentialBucketHistogramAggregation`, flushing one OTLP `/v1/metrics` JSON batch at command completion or `shutdown()`. Replace hand-rolled Prometheus exposition text formatters and regex parsers across `telemetry/metrics.py`, `ai/spend/prometheus.py`, `server/routes/telemetry.py`, `server/service.py`, and `sandbox/metrics.py` with `prometheus-client==0.26.0`, and quiet `httpx`, `httpx2`, and `httpcore` loggers to `WARNING` in Service mode.

#### Key Deliverables:
- [x] **OpenTelemetry SDK `MeterProvider` & Exponential Histograms** (`src/devops_cli/telemetry/tracer.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/main.py`):
  - Replaced `_build_metrics_payload`, `_send_metric`, `_delta_interval`, and `_metric_resource_attributes` with lazy `MeterProvider` and `InMemoryMetricReader` configured with `AggregationTemporality.DELTA` and `View(instrument_type=Histogram, aggregation=ExponentialBucketHistogramAggregation())`.
  -Removed fixed histogram bucket tuples (`_SECONDS`, `_REVIEW_SECONDS`, `_RAG_MILLISECONDS`, `_DAYS`) and `Instrument.bounds`.
  - Flushed accumulated delta metrics once in `main._delegate` `finally:` block and `OTelTelemetryClient.shutdown()`.
- [x] **Prometheus Native Histograms & Dashboard Mean / Sample Count Targets** (`k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/devops-cli.json`, `k8s/monitoring/dashboards/project-metrics.json`, `docs/TELEMETRY.md`):
  - Enabled `enable-feature: native-histograms` in `k8s/monitoring/prometheus-values.yaml`.
  - Added `sum(...) / sum(...)` mean and `_count` sample-count targets to all 5 duration panels in `devops-cli.json` and removed fixed top-bucket cap notes from `devops-cli.json` and `project-metrics.json`.
  - Updated `docs/TELEMETRY.md` to document SDK delta aggregation, exponential histograms, `--enable-feature=native-histograms`, and the `#1132` boundary (`deltatocumulative` `max_stale: 1h` and shared host `service.instance.id`).
- [x] **Service Mode `httpx` Logger Quieting** (`src/devops_cli/server/json_logs.py`, `src/devops_cli/server/service.py`):
  - Set `httpx`, `httpx2`, and `httpcore` loggers to `WARNING` in `service_log_config` and `create_service_app`.
- [x] **`prometheus-client` Exposition & Parsing** (`pyproject.toml`, `uv.lock`, `src/devops_cli/telemetry/metrics.py`, `src/devops_cli/ai/spend/prometheus.py`, `src/devops_cli/server/routes/telemetry.py`, `src/devops_cli/server/service.py`, `src/devops_cli/sandbox/metrics.py`, `src/devops_cli/config/constants.py`):
  - Added `prometheus-client==0.26.0` to `pyproject.toml` and `uv.lock`.
  - Backed `InMemoryMetricsRegistry` with `CollectorRegistry(auto_describe=True)` and standard `Counter`, `Gauge`, and `Histogram` collectors rendered via `generate_latest`.
  - Replaced manual `# HELP` / `# TYPE` formatting in `ai/spend/prometheus.py` and `server/routes/telemetry.py` with custom collectors (`GaugeMetricFamily`, `CounterMetricFamily`) and `generate_latest` with `CONTENT_TYPE_LATEST`.
  - Replaced regex exposition parsing in `sandbox/metrics.py` with `prometheus_client.parser.text_string_to_metric_families` and routed `scrape_prometheus_metrics` through `new_http_client(level=EgressLevel.LOOPBACK, timeout=timeout)`.
  - Removed `CONST_OTEL_AGGREGATION_TEMPORALITY_DELTA` and `CONST_PROMETHEUS_EXPOSITION_METRIC_TYPES` from `src/devops_cli/config/constants.py`.
- [x] **Unit & Integration Tests**:
  - Updated and expanded tests in `tests/test_telemetry_instruments.py`, `tests/test_telemetry.py`, `tests/test_telemetry_metrics.py`, `tests/test_ai_spend_prometheus.py`, `tests/test_sandbox_metrics.py`, `tests/test_server_service.py`, and `tests/test_ai_gateway_tune.py`.
- Pending a person: Deploy updated `k8s/monitoring/prometheus-values.yaml` and `k8s/monitoring/dashboards/` to the live cluster and verify `otelcol_deltatocumulative_datapoints_Total{error="out_of_order"}` stays zero across a multi-persona review.
