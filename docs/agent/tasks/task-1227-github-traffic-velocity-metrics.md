# Task: GitHub Traffic & Velocity Metrics Telemetry Automation (#1227)

**Issue**: [#1227](https://github.com/dan-petty/devops-cli/issues/1227)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/telemetry

## Description
The `Project & Engineering Velocity` Grafana dashboard was not displaying metrics because project velocity and traffic metrics were only collected via manual CLI invocations (`devops gh metrics --emit-telemetry`) and were not exposed on `roadmap-service:8000/metrics` for Prometheus scraping by `k8s-monitoring`. Furthermore, GitHub repository traffic analytics (page views, unique visitors, git clones, unique cloners, top referral sources, and popular content paths) and engagement counts (stargazers, forks) were missing from the project velocity reports.

This deliverable:
1. **GitHub Traffic Telemetry Instruments**: Adds 8 OpenTelemetry instruments to `src/devops_cli/telemetry/instruments.py`:
   - `devops_cli_project_traffic_views_total` (total page views)
   - `devops_cli_project_traffic_views_uniques_total` (unique visitors)
   - `devops_cli_project_traffic_clones_total` (total git clones)
   - `devops_cli_project_traffic_clones_uniques_total` (unique cloners)
   - `devops_cli_project_traffic_referrers_total` (views by referrer source)
   - `devops_cli_project_traffic_paths_total` (views by content path)
   - `devops_cli_project_stars_total` (stargazers count)
   - `devops_cli_project_forks_total` (forks count)
2. **Traffic Analytics Engine & Models**: Implements `TrafficReferrerMetric`, `TrafficPathMetric`, and `TrafficSummaryMetric` Pydantic models in `src/devops_cli/github/metrics.py`, along with decomposed query helpers (`_fetch_traffic_views`, `_fetch_traffic_clones`, `_fetch_traffic_referrers`, `_fetch_traffic_paths`, `_fetch_repo_metadata`, and `get_repository_traffic_metrics`).
3. **In-Memory Registry Recording (`record_project_metrics_in_registry`)**: Implements registry population in `src/devops_cli/github/metrics.py` to record gauges for all release cadence, PR velocity, CI pass rates, milestone progress, and traffic metrics into `InMemoryMetricsRegistry` (`GLOBAL_METRICS`), formatted and scraped directly by Prometheus via `roadmap-service:8000/metrics`.
4. **Automated Collection in `roadmap-service`**: Adds a scheduled `metrics` job to `DEFAULT_DUE_TABLE` in `src/devops_cli/roadmap/run.py` (`interval=15m`, `first_run_due=True`) running `_run_metrics_adapter` on startup and every 15 minutes to continuously refresh repository velocity and traffic telemetry.
5. **Grafana Dashboard Visualization**: Updates `k8s/monitoring/dashboards/project-metrics.json` with a dedicated "GitHub Traffic & Repository Engagement" row featuring stat panels (views, clones, stars, forks) and bargauge panels (top 10 referrers, popular content paths).
6. **CLI Traffic Presentation**: Enhances `devops gh metrics` with traffic overview panels and rich Rich tables for referral sources and popular content paths.

## Acceptance Criteria
- [x] 8 GitHub traffic and engagement instruments added to `src/devops_cli/telemetry/instruments.py` and included in `INSTRUMENTS`.
- [x] Pydantic models and decomposed fetch helpers added to `src/devops_cli/github/metrics.py`.
- [x] `record_project_metrics_in_registry` implemented to set Prometheus gauges in `InMemoryMetricsRegistry`.
- [x] `DEFAULT_DUE_TABLE` in `roadmap-service` executes `metrics` job immediately on startup and every 15 minutes.
- [x] `k8s/monitoring/dashboards/project-metrics.json` updated with GitHub Traffic & Repository Engagement section and panels.
- [x] `devops gh metrics` renders traffic statistics and referral/path tables.
- [x] `tests/test_telemetry_instruments.py` passes verification that all dashboard queries match emitted instruments.
- [x] `tests/test_roadmap_run.py` and `tests/test_github_metrics.py` unit tests pass with 100% coverage.
- [x] Changelog fragment `changelog.d/1227.md` added.
- [x] `uv run devops ci` passes with 100% green status across all quality gates.

## Deliverables
- [x] `src/devops_cli/config/defaults.py` with `DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES`.
- [x] `src/devops_cli/telemetry/instruments.py` with 8 new traffic and engagement instruments.
- [x] `src/devops_cli/telemetry/metrics.py` with `clear_metric`, `record_gauge`, and `__all__`.
- [x] `src/devops_cli/github/metrics.py` with traffic analytics and `record_project_metrics_in_registry`.
- [x] `src/devops_cli/github/__init__.py` exporting traffic models and registry functions.
- [x] `src/devops_cli/commands/gh.py` with traffic summary rendering and in-memory registry updates.
- [x] `src/devops_cli/roadmap/run.py` with `_run_metrics_adapter` and `metrics` job in `DEFAULT_DUE_TABLE`.
- [x] `k8s/monitoring/dashboards/project-metrics.json` with GitHub Traffic & Repository Engagement row and panels.
- [x] `tests/test_github_metrics.py` and `tests/test_roadmap_run.py` comprehensive tests.
- [x] `changelog.d/1227.md` changelog fragment.
- [x] `docs/agent/tasks/task-1227-github-traffic-velocity-metrics.md` task tracking document.
