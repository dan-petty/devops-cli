# Design

## Decisions

- **Send to the Prometheus OTLP receiver.** The collector keeps `deltatocumulative` and sends the running totals with `otlp_http/prometheus`. The OTLP receiver of Prometheus v3.15.0 gets the start time of each point. With `created-timestamp-zero-ingestion`, the head writes a zero sample at the start time of a new stream. It refuses a zero sample that is older than the last sample of the series (`fastRejectOOO`), so a continued stream gets no zero sample in its middle.
- **Keep the `cluster` label.** The remote-write exporter added `cluster` as an external label. The OTLP receiver adds no external label, so `transform/cluster` sets the datapoint attribute `cluster` after `deltatocumulative`. The attribute is the same on each point, so the streams of `deltatocumulative` do not change.
- **Keep the metric names.** `otlp.translation_strategy: UnderscoreEscapingWithoutSuffixes` gives the names that the remote-write exporter gave with the same strategy.
- **Keep `max_stale: 1h`.** The issue asked for 25h. The zero sample alone fixes the counts that a stream restart lost: the SDK gives a delta point the start time of the previous collection, so the zero sample of a restarted stream lands after the last sample of the old stream, and `increase()` counts the new value. A test holds `max_stale` at 1h (see Rejected alternatives).
- **Show the dropped points.** The panel "Delta Points Dropped by deltatocumulative" divides the rate of `otelcol_deltatocumulative_datapoints{error!=""}` by the rate of all points, by error. The processor records `limit`, or the type of the delta error (an older start, or an out-of-order point). The line is at 0.5 %.

## Rejected alternatives

- **`max_stale: 25h`.** The rules of the groups `roadmap-service`, `roadmap-service-activity` and `crawl4ai` in `k8s/monitoring/prometheus-values.yaml` count a series with no sample in the hour before by its last value (`last_over_time(...[1h]) unless last_over_time(...[1h] offset 1h)`, #2505). With max_stale 1h, such a series is a new stream, and its last value is the count of the hour. With 25h, a series that is idle for 1 h to 25 h keeps its old total. For example, a GitHub request series of the Service with a total of 50 that gets one request after 3 h reads 51 in `RoadmapServiceGitHubRequestsHigh`. A change of each rule to read the sample before the hour is a second fix on the #2505 fix, and the zero sample already gives the counts that 25h was to keep.
- **Remote write 2.0 through the exporter feature gate.** The exporter README at v0.161.0 calls it "In Development and is only partially implemented, thus, not ready for usage", and it needs the feature gate `exporter.prometheusremotewritexporter.enableSendingRW2`.
- **`otlp-native-delta-ingestion` of Prometheus.** `cmd/prometheus/main.go` at v3.15.0 logs "Delta support is in an early stage of development" for it, and it stores raw deltas that `increase()` does not add up.
- **`otlp-deltatocumulative` of Prometheus.** It keeps the same state in memory as the collector processor, in the server, and the collector would still need a path for the other signals.
- **A `service.instance.id` for each process.** Each command would write a new series with one sample, and the series count would grow with each command.
