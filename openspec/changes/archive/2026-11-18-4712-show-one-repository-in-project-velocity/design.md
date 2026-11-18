# Design

## Decisions
- Define `job` and `repo` as single-select template variables in `k8s/devops/dashboards/project-metrics.json`.
  Single selection ensures that each panel displays data for exactly one target repository and job.
- Set default values to `roadmap-service` for `job` and `dan-petty/devops-cli` for `repo`.
- Use exact matchers `job="$job"` and `repo="$repo"` on every Prometheus metric target.
- Replace `$__range` with `[1h]` to ensure consistent instant queries and rate calculations.
- Merge Panels 7 and 8 into a unified bar chart that compares commits and pull requests per release.
- Use `groupingToMatrix` transformation for workflow status in Panel 11 to display workflow matrices cleanly.
- Verify queries with Promtool unit tests in `tests/fixtures/dashboard_queries/project-metrics.yaml`.
- Enforce variable existence and query filters with an invariant test in `tests/prometheus/test_k8s_monitoring_dashboards.py`.

## Rejected alternatives
- Multi-value repository selection: Rejected because velocity panels aggregate release metrics across series, which causes incorrect sums across different repositories.
- Keep `$__range`: Rejected because instant queries require fixed lookback windows for reliable rate calculations.
- Retain separate commit and pull request panels: Rejected because viewing both metrics on one release axis improves comparison.
