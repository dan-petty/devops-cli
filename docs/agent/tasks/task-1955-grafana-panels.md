# Task: Grafana Panels Hold Data, and k8s-monitoring Uses the Chart's Documented Settings (#1955)

**Issue**: [#1955](https://github.com/dan-petty/devops-cli/issues/1955)
**Scope**: scope/monitoring, scope/telemetry
**Feasibility**: On 2026-10-23 a read-only probe ran every panel query of 14 dashboards through Grafana. The Global CPU query returned 0 of 241 points with `[1m]` and 241 with `[4m]`. Prometheus held only the bare native histogram `devops_cli_command_duration_seconds`, and `histogram_quantile`, `histogram_avg` and `histogram_count` over it returned each command. `up` showed two Pyroscope targets and two kube-state-metrics targets. The Prometheus log said that `--enable-feature=native-histograms` is a no-op. Pyroscope listed `goroutine:goroutine:count:goroutine:count`, and Loki kept `pod` as structured metadata. `helm template` of grafana/k8s-monitoring 4.5.2 with the old and new values showed only the intended changes.

## Description

- [x] **Rate windows** (`k8s/monitoring/grafana-values.yaml`, `k8s-monitoring-values.yaml`): the Prometheus datasource sets `jsonData.timeInterval: 60s`, the k8s-monitoring scrape interval, which `global.scrapeInterval` now names. Grafana then makes `$__rate_interval` at least 4m, so a rate window holds two samples.
- [x] **Native histograms** (`telemetry/instruments.py`, `devops-cli.json`, `project-metrics.json`): an instrument is stored under its own name, and the latency, mean and count panels use `histogram_quantile`, `histogram_avg` and `histogram_count`. Panels 3 to 5 of the Project dashboard change because they read the same instruments; its gauges stay with #974. The generated `docs/TELEMETRY.md` and the Prometheus knowledge base article say the same.
- [x] **Pods view**: the `pod` variable holds one pod, so its nine exact `pod="$pod"` panels match it.
- [x] **Nodes view**: the pod CPU and memory panels sum the container series (`image!="", container!=""`), because the chart drops the empty-image series.
- [x] **node-exporter**: the `processes` and `tcpstat` collectors run, for the process and TCP panels of Node Exporter Full.
- [x] **Single panels**: the goroutine profile id in `pyroscope.json`, an "All" default for the DCGM `instance` variable, the SRE Loki panel filters `pod` after the stream selector, and the SRE `pod` variable lists the pods of the namespace.
- [x] **Chart settings**: Loki and Pyroscope write `cluster` only (the Loki half is #1657); kube-state-metrics is discovered by its Service; the Alloy integration also scrapes `alloy-profiles`; alloy-logs keeps its read positions with the `host-storage` preset; alloy-profiles uses the `root` preset with `hostPID` instead of the deprecated `privileged` preset; the Pyroscope ServiceMonitor drops the headless Service; Prometheus drops the no-op `native-histograms` flag.
- [x] **Tests**: no dashboard matches a multi-value variable exactly, selects `image=""`, or reads a `_bucket`, `_sum` or `_count` of a devops-cli histogram; the datasource interval equals the scrape interval; each target is scraped once, and each destination writes `cluster` only.
- Not done: the alloy-metrics write-ahead log has no volume claim, so a restart loses unsent samples. A StatefulSet cannot change its `volumeClaimTemplates` in place. Intake did not file the follow-up on 2026-10-23, because the agent filing quota of the window was used.
- Not changed: the Tempo integration sets `job` to `<namespace>/<component>` by design, and no dashboard reads it.
- Pending a person: after Argo CD syncs `monitoring`, `grafana` and `k8s-monitoring`, Node Exporter Full, the Kubernetes views and the devops-cli dashboard show data in their rate, latency and pod panels.
