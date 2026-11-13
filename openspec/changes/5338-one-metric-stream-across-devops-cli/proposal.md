# Proposal

## Why

#4697 removed `host.name` from the metric Resource of the tracer. A devops-cli build from before that change still sends `host.name`, and the collector's `deltatocumulative` keys a stream by every resource attribute. So an old build and a new build of one workload write two running totals into one Prometheus series, and the counts in that series are wrong (#5338). The alert `DevopsCliMetricStreamsShareSeries` names a cause that cannot raise it, its runbook action is in a table cell that GFM does not render, and no test fails when the workstation default of `service.instance.id` or the allowlist filter of the metric Resource changes.

## What Changes

- Add the processor `transform/metric_resource` to the metrics pipeline of `k8s/otel/values.yaml`, after `memory_limiter` and before `deltatocumulative`. It deletes the resource attribute `host.name` where `telemetry.sdk.name` is `devops-cli-otel`, so every devops-cli build, old or new, sends one stream for each workload.
- Rewrite the description of `DevopsCliMetricStreamsShareSeries` in `k8s/monitoring/prometheus-values.yaml`: compare the labels of the two `target_info` series. A different `telemetry_sdk_*` label is a second SDK. Another different label is a build with another metric Resource. A `host_name` label shows metrics that did not go through the collector rule. The alert clears 15 minutes after the old writer stops.
- Rewrite the row of the alert in the Alerting table of `k8s/README.md`, with the action in the "Fires when" cell. Move the action of `ResearchCriticalFindings`, `ClaudeSpendDailyHigh` and `HostedSpendDailyHigh` into that cell too, because those rows have the same fifth cell that GFM drops.
- Parse the Alerting table with markdown-it-py in `tests/prometheus/test_k8s_monitoring_alerting.py`, so a row with more cells than the header fails, and read the alert row from the rendered cells.
- Pin the promtool cases of `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`: no alert at 29 minutes and an alert at 30 minutes, quiet at 34 minutes of a pod change, a quiet job outside the matcher, and two sparse writers that only the 15 minute lookback joins.
- Add a test of the workstation default (no `OTEL_RESOURCE_ATTRIBUTES`) and put `host.name` and `k8s.pod.name` in `OTEL_RESOURCE_ATTRIBUTES` of the two-pod test, in `tests/telemetry/test_telemetry.py`. Add a test of the collector rule to `tests/telemetry/test_telemetry_instruments.py`, and give `test_counters_are_monotonic_deltas_from_the_workload_not_the_process` the name of what it checks.
- Add the collector rule and the note on Job pods that send at the same time to the metric paragraph of `src/devops_cli/docs/generator.py`, and regenerate `docs/TELEMETRY.md`.
- The change carries a spec delta: the collector pipeline, the alert text and the runbook row are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: The metric Resource holds only stable attributes, The metric Resource reads the configured instance, Two metric streams in one Prometheus series fire an alert, One stream and a short overlap stay quiet, The rule set, the case file and the runbook list the alert, and the new requirement The collector deletes the host name of devops-cli metrics before it adds the deltas.
- `monitoring-collectors`: The OpenTelemetry collector sends metrics to the Prometheus OTLP receiver. The metrics pipeline now has a resource statement and a datapoint statement, so the scenario names the one datapoint statement that sets `cluster`.

## Impact

- Manifests: `k8s/otel/values.yaml` (the collector Deployment rolls out once at the merge, because the chart hashes its config into the pod template), `k8s/monitoring/prometheus-values.yaml` (the Prometheus server reloads its rules, and no pod restarts).
- Code: `src/devops_cli/docs/generator.py`.
- Documents: `k8s/README.md`, `docs/TELEMETRY.md`.
- Tests: `tests/telemetry/test_telemetry.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/metric_streams_tests.yaml`.
- No image change. The collector rule needs no new devops-cli code, so it can go live at the merge.

## Feasibility

- origin/main at 9717c9bf9: the metrics pipeline of `k8s/otel/values.yaml` is `[memory_limiter, deltatocumulative, transform/cluster, batch]`, and no processor changes `host.name`. `git grep host_name -- k8s` finds no dashboard or rule that reads the label.
- Prometheus through Grafana, 2026-11-13 03:46Z: over 16 hours, `max_over_time(count by (job, instance) (last_over_time(target_info{job=~"devops-cli.*|roadmap-service"}[15m]))[16h:5m])` was 2 for the workstation instance of job `devops-cli`, 2 for two runner pod instances of `devops-cli-job`, and 3 for `roadmap-service`. In each pair, the old-build series has `host_name` and the new-build series has no `host_name`. The labels `os_type`, `telemetry_sdk_language` and `telemetry_sdk_name` are equal. `ALERTS{alertname="DevopsCliMetricStreamsShareSeries"}` was firing for the workstation pair in the last 3 hours.
- Over 7 days, every OTLP `target_info` series has `telemetry_sdk_name="devops-cli-otel"` (jobs `devops-cli`, `devops-cli-job`, `devops-mcp-server`, `roadmap-service`, `roadmap-fix-plan-validation`, `roadmap-implement-check`). The tracer sets that name in `_ensure_meter` of `src/devops_cli/telemetry/tracer.py`, and old builds send the same name.
- Upstream source, opentelemetry-collector-contrib v0.163.0: `internal/exp/metrics/identity/resource.go` gives `OfResource(r) = Resource{attrs: xhash.MapHash(r.Attributes())}`, so the stream key holds every resource attribute. `pkg/ottl/ottlfuncs/README.md` documents `delete_key(target, key)` with the example `delete_key(resource.attributes, ...)`. `processor/transformprocessor/README.md` allows the `resource` context in `metric_statements`.
- `helm template` of chart `opentelemetry-collector` 0.178.3 (the version of `k8s/argocd/apps/otel-collector.yaml`) renders the image `otel/opentelemetry-collector-contrib:0.163.2`.
- `sum by (error) (increase(otelcol_deltatocumulative_datapoints[24h]))`: about 136,000 points added, 219 `ErrOutOfOrder` and 5 `ErrOlderStart`.
- The Alerting table of `k8s/README.md` has 46 body rows. 4 rows have 5 cells against a 4-column header (count by `awk` of the cells of each row): `DevopsCliMetricStreamsShareSeries`, `ResearchCriticalFindings`, `ClaudeSpendDailyHigh` and `HostedSpendDailyHigh`. The new test covers every row, so this change fixes all 4.
- The test of the workstation default and the two-pod test with `host.name` in `OTEL_RESOURCE_ATTRIBUTES` pass on origin/main by design: they guard behavior that main has. A mutation proves each: `service.instance.id` set to a constant, and the metric Resource built without the allowlist filter.

## Existing Tool Considered

The OpenTelemetry Collector `transform` processor (OTTL `delete_key`) removes the attribute, promtool tests the alert, and markdown-it-py, a dependency of the project, parses the README table the way GFM renders it. The change builds no tool of its own. It deletes the hand split of the README row (`strip("|").split(" | ")`) in `tests/prometheus/test_k8s_monitoring_alerting.py`.
