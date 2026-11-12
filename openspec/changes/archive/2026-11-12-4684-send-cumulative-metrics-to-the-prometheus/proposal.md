# Proposal: #4684

## Why

No devops-cli OTLP series starts with a zero sample (#4684): `count(min_over_time(devops_cli_github_requests_total[24h]) == 0)` is empty. So `increase()` does not count the first sample of a new stream. Runner Jobs lose 18 % of their commands, and a stream that starts again with the same total as before (a retitle row series, 344 equal consecutive samples of the Service in 24 h) adds nothing. The setting `remote_write_version: 2` of the collector has no effect: the `prometheusremotewriteexporter` config at contrib v0.161.0 has no such key, so the collector sends remote write 1.0 with no start time.

## What Changes

- The metrics pipeline of `k8s/otel/values.yaml` sends to the exporter `otlp_http/prometheus` at `/api/v1/otlp/v1/metrics` of the Prometheus server. The exporter `prometheus_remote_write` and its dead key `remote_write_version` go.
- The new processor `transform/cluster` sets the datapoint attribute `cluster`, because the OTLP receiver adds no external label.
- `k8s/monitoring/prometheus-values.yaml` turns on `web.enable-otlp-receiver` and sets `otlp.translation_strategy: UnderscoreEscapingWithoutSuffixes`. It keeps `created-timestamp-zero-ingestion`, the remote write receiver of Alloy and the out-of-order window.
- `deltatocumulative` keeps `max_stale: 1h`. A test holds it there, because the roadmap-service rules read a series with no sample in the hour before as a new stream (design.md).
- `otel-collector.json` gets the row "Processors" with the panel "Delta Points Dropped by deltatocumulative": the dropped share by error, with a line at 0.5 %.
- `docs/TELEMETRY.md` and its generator text name the OTLP receiver path. The collector metrics fixture loses the remote-write exporter families.

The change is observable in the manifests, so it has a spec delta. It fits one pull request.

## Capabilities

- `monitoring-collectors`: two ADDED requirements, for the metrics export path and for `max_stale`.

## Impact

- Each devops-cli OTLP series breaks one time at the rollout: the OTLP receiver writes no `otel_scope_name` or `otel_scope_version` label (`promote_scope_metadata` is false by default). No rule, panel or test selects these labels.
- The collector restarts with the new configuration, so each stream starts again from zero, now with a zero sample.
- `target_info` of devops-cli gets no `cluster` label. No rule, panel or test reads `target_info`.

## Feasibility

Confirmed against upstream source at the deployed versions (charts `prometheus` 29.35.0 with Prometheus v3.15.0, `opentelemetry-collector` 0.175.0 with contrib v0.161.0):

- `exporter/prometheusremotewriteexporter/config.go` at v0.161.0 has no `remote_write_version` key. Remote write 2.0 needs `protobuf_message` and a feature gate.
- `storage/remote/otlptranslator/prometheusremotewrite/number_data_points.go` at v3.15.0 passes the start time of each point to `Append`. With `created-timestamp-zero-ingestion`, `cmd/prometheus/main.go` sets `EnableSTAsZeroSample`. `tsdb/head_append_v2.go` (lines 150 and 362 to 410) then writes a zero sample at that time and refuses it when it is out of order, so a zero sample cannot land inside a series.
- `config/config.go` at v3.15.0 accepts `UnderscoreEscapingWithoutSuffixes`. The chart template `templates/cm.yaml` writes `server.otlp` as the `otlp` block, and `templates/deploy.yaml` writes each `server.extraArgs` key as a flag.
- `exporter/otlphttpexporter` at v0.161.0 has the type `otlp_http` and the key `metrics_endpoint`. `storage/remote/codec.go` of Prometheus accepts its gzip body.
- `helper.go` of the Prometheus translator sets `job` and `instance` from the resource after the attributes, as the remote-write exporter did.
- The OpenTelemetry Python SDK 1.45.1 sets the start time of a delta point to the previous collection time. So a stream that starts again after `max_stale` gets its zero sample after the last sample of the old stream.

## Existing Tool Considered

The Prometheus OTLP receiver (`web.enable-otlp-receiver`) and the collector `otlp_http` exporter are open tools with a standard interface. The change adds no code; only configuration, a panel, a test and documents change.
