# Task: Classify Project Metrics and Upstream Status Snapshot Instruments as Gauges (#1253)

**Issue**: [#1253](https://github.com/dan-petty/devops-cli/issues/1253)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/telemetry

## Description
Investigate and resolve metric inflation across panels on the Project & Engineering Velocity Grafana dashboard (`project-metrics.json`, UID `devops-project-metrics`). Point-in-time snapshot metrics (such as GitHub issue items by milestone, releases, commits per release, merged PRs per release, 14-day traffic view counts, stargazers, forks, and upstream service operational status codes) were declared as `InstrumentKind.COUNTER` rather than gauges.

Because short-lived CLI processes emit OTLP delta metrics, the OpenTelemetry Collector's `deltatocumulative` processor accumulated snapshot values across periodic emissions rather than recording current states. This caused the Project & Engineering Velocity Grafana dashboard to report vastly inflated numbers (e.g. 34,000+ closed items instead of ~120).

## Key Changes
1. **InstrumentKind & Tracer Gauge Support**:
   - Added `InstrumentKind.GAUGE` to `src/devops_cli/telemetry/instruments.py`.
   - Added `record_gauge` method to `OTelTelemetryClient` and module-level `record_gauge` helper in `src/devops_cli/telemetry/tracer.py`.
   - Updated `emit()` in `src/devops_cli/telemetry/instruments.py` to route `InstrumentKind.GAUGE` instruments to `tracer.record_gauge(...)`.
2. **Reclassify Snapshot Instruments**:
   - Reclassified point-in-time inventory instruments (`PROJECT_ITEMS_TOTAL`, `PROJECT_COMMITS_TOTAL`, `PROJECT_PRS_TOTAL`, `PROJECT_CI_RUNS_TOTAL`, `PROJECT_RELEASES_TOTAL`, `PROJECT_STARS_TOTAL`, `PROJECT_FORKS_TOTAL`, `PROJECT_TRAFFIC_*`) from `InstrumentKind.COUNTER` to `InstrumentKind.GAUGE`.
   - Reclassified upstream cloud platform operational status severity codes (`UPSTREAM_SERVICE_STATUS`, `UPSTREAM_COMPONENT_STATUS`) from `InstrumentKind.COUNTER` to `InstrumentKind.GAUGE`.
3. **Dashboard PromQL Calculation**:
   - Updated Panel 5 in `k8s/monitoring/dashboards/project-metrics.json` to compute interval per release by dividing release interval sum by count (`sum by (release) (...) / clamp_min(sum by (release) (..._count), 1)`).
4. **Documentation & Verification**:
   - Updated `docs/TELEMETRY.md` table to list reclassified instruments as `Gauge`.
   - Added unit test `test_gauges_are_recorded_as_instantaneous_values` in `tests/test_telemetry_instruments.py` verifying that gauges emit instantaneous point-in-time values rather than accumulating deltas.
   - Upgraded `multidict` to `6.9.1` to resolve security advisory `GHSA-54p9-h82j-f925`.
   - Verified all quality gates pass via `uv run devops ci` and `uv run devops grafana dashboards lint k8s/monitoring/dashboards`.

## Acceptance Criteria
- [x] `InstrumentKind.GAUGE` added and supported by `emit()` and `tracer.record_gauge()`.
- [x] All point-in-time inventory and status code instruments reclassified from `COUNTER` to `GAUGE`.
- [x] Panel 5 in `project-metrics.json` computes release interval per release using sum divided by count.
- [x] `docs/TELEMETRY.md` and changelog fragment `changelog.d/1253.md` updated.
- [x] Unit test suite in `tests/test_telemetry_instruments.py` verifies gauge recording behavior.
- [x] Quality gate `uv run devops ci` completes with 100% passing status.
