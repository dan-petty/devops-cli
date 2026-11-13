# Tasks

## 1. Delete the host name of devops-cli metrics in the collector

Kind: behavior. Reads: `k8s/otel/values.yaml`, `src/devops_cli/telemetry/tracer.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `k8s/otel/values.yaml`, `tests/telemetry/test_telemetry_instruments.py`, `tests/commands/k8s/test_k8s_monitoring_integration.py`.

- [x] 1.1 Add `test_the_collector_deletes_the_host_name_of_devops_cli_metrics_before_it_adds_them_up` to `tests/telemetry/test_telemetry_instruments.py`: the processors before `deltatocumulative` are `memory_limiter` and `transform/metric_resource`, and its one resource statement deletes `host.name` where `telemetry.sdk.name` equals the SDK name of an exported metric
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [x] 1.2 Add `transform/metric_resource` with `error_mode: ignore` to `k8s/otel/values.yaml` and put it in the metrics pipeline after `memory_limiter` and before `deltatocumulative`. Rename `test_counters_are_monotonic_deltas_from_the_host_not_the_process` to `test_counters_are_monotonic_deltas_from_the_workload_not_the_process`. In `test_otel_collector_sends_metrics_to_the_prometheus_otlp_receiver` of `tests/commands/k8s/test_k8s_monitoring_integration.py`, read only the datapoint statements, because the resource statement has its own test
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 2. Guard the metric Resource of the tracer

Kind: test-only. Reads: `src/devops_cli/telemetry/tracer.py`, `tests/telemetry/test_telemetry.py`. Changes: `tests/telemetry/test_telemetry.py`.

- [x] 2.1 Add `test_a_workstation_metric_resource_names_its_host_as_the_instance`: with no `OTEL_RESOURCE_ATTRIBUTES` and a known `platform.node()`, the metric Resource equals the literal allowlisted dict with the host name as `service.instance.id`. In `test_two_tracers_with_one_instance_send_equal_metric_resources`, put `host.name` and `k8s.pod.name` of each pod in `OTEL_RESOURCE_ATTRIBUTES`. Prove each test with a mutation of `_ensure_meter` in `src/devops_cli/telemetry/tracer.py` that is not committed: a constant `service.instance.id`, and the Resource built without the filter
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py` passes

## 3. Rewrite the alert and pin its promtool cases

Kind: behavior. Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`.

- [x] 3.1 In `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`, set the new description, check the firing case at 29 and 30 minutes, check the pod-change case at 34 minutes, and add a quiet case for the job `llm-gateway` and a firing case for two sparse writers
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 3.2 Rewrite the description of `DevopsCliMetricStreamsShareSeries` in `k8s/monitoring/prometheus-values.yaml`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 4. Render each cell of the Alerting table

Kind: behavior. Reads: `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [x] 4.1 Add `test_each_row_of_the_alerting_table_renders_every_cell`, and make `test_the_metric_streams_alert_has_a_row_in_the_readme` read the rendered cells of the row, both through markdown-it-py
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 4.2 Rewrite the row of `DevopsCliMetricStreamsShareSeries` in `k8s/README.md` with the action in the "Fires when" cell, and move the fifth cell of `ResearchCriticalFindings`, `ClaudeSpendDailyHigh` and `HostedSpendDailyHigh` into that cell
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 5. Documents

Kind: documents. Reads: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [x] 5.1 Add the collector rule and the note on Job pods that send at the same time to the metric paragraph of `src/devops_cli/docs/generator.py`, and regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
