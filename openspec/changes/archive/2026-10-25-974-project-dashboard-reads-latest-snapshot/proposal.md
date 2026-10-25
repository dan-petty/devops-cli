# Proposal

## Why

Issue #974, re-scoped on 2026-10-25. Most panels of the Project & Engineering Velocity dashboard show no data.

The project metrics are gauges (#1253), and the roadmap Service sends them every 15 minutes in its `metrics` job. But 14 panels read a gauge as a plain selector, or through `max(` or `sum(` with no range function. Prometheus finds a plain selector only within five minutes of a sample, so these panels are empty for about two thirds of each interval, and all the time while nothing sends a snapshot. The stat panels add `or vector(0)`, so they show a false 0. The dashboard invariant that reads each series through a range function skipped this dashboard, so no test caught it.

The 13 project gauges also end in `_total`, a suffix that Prometheus keeps for counters, so each consumer reads them as counters.

## What Changes

- Each gauge panel of `k8s/monitoring/dashboards/project-metrics.json` reads `last_over_time(<metric>[$__range])`, grouped by the same labels as before, and drops `or vector(0)`. Its description says that it shows the latest value of each series in the time range, and no data when none was sent in it.
- The 13 project gauges drop `_total`, in `src/devops_cli/telemetry/instruments.py` (names and constants), `src/devops_cli/github/metrics.py`, the dashboard and `docs/TELEMETRY.md`. Pre-1.0, nothing is kept for compatibility.
- `tests/test_telemetry_instruments.py`: the invariant reads each series of each devops-cli dashboard by its kind, with no exception for this dashboard: a counter through `rate(` or `increase(`, a gauge through `last_over_time(`, a histogram through either. A new invariant: only a counter name ends in `_total`.
- `docs/TELEMETRY.md`, which `src/devops_cli/docs/generator.py` writes, says how a dashboard reads a gauge, and that no gauge name ends in `_total`.
- The dashboard and the metric names are observable, so the change has a spec delta: the new capability `project-metrics-dashboard`.
- The change fits in one pull request.

Moved out of #974: the emission on command use (the roadmap Service's `metrics` job sends the snapshot) and the two gauges that a comment folded in from #1400 (a separate item).

## Capabilities

### New Capabilities

- `project-metrics-dashboard`: how the project dashboard reads the project snapshot, and how devops-cli names its gauges and counters.

### Modified Capabilities

None.

## Impact

- `k8s/monitoring/dashboards/project-metrics.json`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/github/metrics.py`, `src/devops_cli/docs/generator.py` and the generated `docs/TELEMETRY.md`.
- `tests/test_telemetry_instruments.py`, `tests/test_github_metrics.py`, `tests/test_roadmap_run.py`.

## Feasibility

- `main` at 28c16079: the 13 project instruments are `InstrumentKind.GAUGE` and end in `_total`; `devops_cli_project_release_interval_days` is a histogram; `_run_metrics_adapter` in `src/devops_cli/roadmap/run.py` sends the snapshot every `DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES` (15); panels 2, 7, 8, 10, 11, 13, 14 and 16 to 23 read the gauges with no range function.
- The read-only probe of 2026-10-23 on the lab Prometheus (comment on #974): 6 of 20 panels had data; `sum by (release) (last_over_time(devops_cli_project_commits_total[$__range]))` returned 28 series at the 30-day default range, while the plain selectors returned nothing outside five minutes of an emission.
- The kind-aware rule over the three devops-cli dashboards finds misreads in `project-metrics.json` only, so it applies to all of them with no exception.

## Existing Tool Considered

Prometheus' own `last_over_time` reads the latest sample of a gauge, and its naming rules keep `_total` for counters. The change builds nothing; it corrects the queries and the names.
