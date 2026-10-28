# Proposal

## Why

Issue #2505: a review of the rule group `roadmap-service` (#2472) found two gaps, and a check of the same rules found a third.

- `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceModelRequestsHigh` use `sum(increase(...[1h]))`. A series has no zero sample before its first count, so `increase()` does not count the first value. The OTLP collector starts a stream again from zero when the Service comes back, when a series has no sample for an hour, when the collector restarts, and when a new label set appears. The rules then miss a real overrun.
- `RoadmapServiceLaneStalled` has no input for a lane of a new pod until the lane starts a job. After a rollout, a lane that starts no job for 2 hours gives no alert.
- The correction of `RoadmapServiceJobsFailing` reads the series 1 hour ago with the 5-minute lookback. A sparse error series from before the hour adds all of its count, and a new series with one sample gives no result.

## What Changes

- The rules `RoadmapServiceJobsFailing`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceModelRequestsHigh` in `k8s/monitoring/prometheus-values.yaml` count each series of the last hour in one way. A series with no sample in the hour before started in the hour, and gives its last value. Every other series gives its `increase()`.
- `RepoWorker.start` in `src/devops_cli/server/service.py` sets the gauge `devops_cli_service_job_start_timestamp_seconds` of its lane to the time the worker starts. The first job of the lane sets it again. `RoadmapServiceLaneStalled` does not change.
- `k8s/README.md`, "Roadmap service", "Alerts", says how the counts read a new series and when the 2 hours of a new pod start.
- `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` gets a promtool case for each gap. `tests/test_k8s_monitoring_alerting.py` pins the new expressions, and `tests/test_server_service.py` checks the gauge at the start of a worker.
- The change alters a manifest and the metrics of the Service, so it carries a spec delta. It modifies two requirements of the capability `roadmap-service-alerts`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-alerts`: failed jobs, a stalled lane and the request volume count a series that starts in the hour, and a lane of a new pod.

## Impact

- Manifest: `k8s/monitoring/prometheus-values.yaml`. Argo CD's `prometheus` Application applies it after the merge. The deployment of the Service is at `replicas: 0`, so no rule of the group fires until the Service runs again.
- Code: `src/devops_cli/server/service.py` and `src/devops_cli/config/constants.py`. The `/metrics` of a new pod has a job start series for each lane of each repository before the first job.
- Related: #2506 is the cause in the pipeline. Prometheus records no zero sample at the start of a series that the collector sends, so `increase()` drops the first export in every query, not only in these rules.

## Feasibility

Checked on 2026-10-28 with promtool 3.15.0 (`devops install-tools --tool promtool`), the version of the Prometheus server of the cluster, and read-only, through the Grafana MCP tools, against that server.

- **The gaps.** `promtool test rules` over the rules at `origin/main` 0137f231 gives no alert for 520 GitHub requests and 415 model requests of a stream that starts in the hour, and no `RoadmapServiceLaneStalled` for a lane of a replaced pod at 200 minutes. It gives `RoadmapServiceJobsFailing` with "8 model jobs" for an error series with samples 5, 6 and 7 at 50, 70 and 110 minutes (2 failed jobs in the hour), and no alert for a new error series with one sample of 3.
- **No zero sample.** The Prometheus server runs with `--enable-feature=created-timestamp-zero-ingestion`, and the collector has `export_created_metric: true` (#2039). The three `devops_cli_github_requests_total` series that started on 2026-10-28 start at 1, and Prometheus has no `devops_cli_*_created` series in 10 days. The OTLP series are sparse: a `devops_cli_ai_requests_total` series of a workstation has samples hours apart.
- **The new expression on real samples.** At 2026-10-10T23:05:00Z, when the jobs of 16 repository and lane pairs failed at each round, the new `RoadmapServiceJobsFailing` expression finds the 16 pairs, 15 with the exact count 3. At 2026-10-10T20:00:00Z it finds none. Over 30 days at 5-minute steps, the old and the new expressions fire at the same 657 steps, because the scraped error series have a sample at each scrape. The highest count of the new model expression in 30 days is 54, and of the old one 53.3.
- **The gauge.** `devops_cli_service_job_start_timestamp_seconds` is a gauge of `GLOBAL_METRICS` on the `/metrics` of the pod. `RepoWorker._execute_batch` sets it when a job starts, and no code sets it before.

## Existing Tool Considered

promtool tests the rules, as for #2472. Prometheus's created timestamps (`created-timestamp-zero-ingestion`) are the tool that gives a series a zero sample at its start, and with them plain `increase()` counts the first value. They do not reach Prometheus on the path of the collector (remote write 1.0), so they cannot cover this need now. #2506 fixes that path. The Prometheus instrumentation guide says to export a series that is known to exist before its first event, and the worker does that for its lane. The change builds no tool and deletes the old correction of `RoadmapServiceJobsFailing`.
