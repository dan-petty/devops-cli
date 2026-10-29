# Design

## The failing-send rule

`OtelCollectorExportFailing` is `increase(<send_failed counter>[15m]) > 0` for 15 minutes, summed by exporter, for each of the three signals, joined with `or`. `label_replace` adds `data_type` with the value that the queue gauges use, so both rules name the exporter and the signal. The form is the one of the Alloy rules in `homelab-telemetry-pipeline`.

The rule fires when the counter grew in the 15 minutes before the first evaluation and in the 15 minutes before the last. One failed send keeps the increase above 0 for 14 minutes, which is shorter than the wait, so it stays quiet. A failure that goes on fires after about 16 minutes.

A `send_failed` counter starts at the first failed send, and `increase()` does not count the first value of a new series. So a failure that goes on fires one scrape later than it would on a counter that already exists. The rule is for a failure that goes on, so this is accepted.

## Rejected alternatives

- **Count the first value of a new counter, as `RoadmapServiceWebhooksRejected` does (#2505).** That rule must count a burst of forged deliveries in a new label set. Here a short burst is not the target: the 15-minute wait already ignores it, and the form would repeat a three-line expression for each of the three signals.
- **`rate(...[5m]) > 0` for 15 minutes.** It fires only on failures in each 5-minute window, which is closer to "fails for 15 minutes". The issue and the Alloy rules use `increase(...[15m])`, and one form for every drop rule is easier to read in the Alerting table.
- **Rules in `homelab-telemetry-pipeline`.** Two tests of that group check each series against the allow list of k8s-monitoring's Alloy integration. The collector is scraped by the Prometheus server, not through Alloy, so its rules are in a group of their own.
- **A `node` label.** The issue names it, and the refinement asked a person to choose. An export failure is the collector's: its pod can move to any node, and a node silence for planned maintenance must not hide a lost trace pipeline. The rules sum by exporter, which also removes the pod's `node`. `k8s/README.md`, Planned maintenance, already says that some cluster-wide alerts have no `node` label.
- **A rule on `otelcol_exporter_enqueue_failed_spans`.** The issue names it as an option. A full queue that refuses new spans already fires `OtelCollectorExportQueueFull`, and a send that fails fires `OtelCollectorExportFailing`, so a third rule adds no new case.
