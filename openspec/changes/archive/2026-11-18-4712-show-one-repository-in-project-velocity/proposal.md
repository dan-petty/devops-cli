# Proposal: #4712

## Why
The Project Velocity dashboard aggregated metrics across multiple repositories and jobs into single charts.
When Prometheus collected samples from multiple repositories, panels mixed data from different sources.
The dashboard also used range queries and variable ranges that produced confusing velocity charts.

## What Changes
- Add `job` and `repo` single-select template variables to `k8s/devops/dashboards/project-metrics.json`.
- Add `job="$job"` and `repo="$repo"` label matchers to all Prometheus metric queries.
- Replace `$__range` duration tokens with a fixed `[1h]` window.
- Convert release interval panels to instant quantiles.
- Merge commit and pull request panels into one bar chart.
- Calculate instant continuous integration pass rate with clear threshold colors.
- Display workflow runs in a horizontal matrix.
- Filter item age metrics by state and plan.
- Update Promtool test fixtures and invariant dashboard tests.
- This change alters dashboard configuration and test assertions without changing the CLI interface, so it sets `skip_specs: true`.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None. The dashboard configuration is internal monitoring metadata and not an external CLI capability.

## Impact
- Operators can select a specific job and repository to view isolated project velocity metrics.
- Panels show accurate data without mixing samples from multiple repositories.

## Feasibility
- Verified Prometheus target queries with `promtool` in `tests/fixtures/dashboard_queries/project-metrics.yaml`.
- Verified dashboard template variables and query constraints in `tests/prometheus/test_k8s_monitoring_dashboards.py`.
- Verified dashboard structure using Grafana linting utilities.

## Existing Tool Considered
Grafana dashboard templating and Prometheus label filtering are the standard tools for multi-tenant isolation.
