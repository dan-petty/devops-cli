# Design

## Decisions

- **Use two gauges and one histogram, and no counter, for the new instruments.**: A gauge holds a point-in-time count or age, which is what unchecked items and the oldest check age are. A histogram holds the distribution of searches per check. A counter only increases and cannot express either gauge.
- **Record the gauges from the alternatives job at the end of each round, by repository.**: The job already reads every open item and its check, so it holds both numbers with no extra GitHub request. The repository label comes from the round's repository.
- **Record the searches-per-check histogram once for each written check, labelled by verdict.**: The job already counts each written check by verdict in `devops_cli_roadmap_alternatives_total`. The histogram sits at the same write, so a check that is skipped or fails records nothing.
- **Express the alert as `increase(devops_cli_firecrawl_searches_total[3d]) == 0 and devops_cli_roadmap_alternatives_unchecked_items > 0`.**: It states the condition directly: no search in 3 days while unchecked items exist. The repository label of the gauge names the repository in the annotation.
- **Add the panel to `k8s/monitoring/dashboards/devops-cli.json`.**: That file is the Roadmap dashboard of the project, and the existing roadmap panels are there.

## Rejected alternatives

- **Use a counter for all three instruments.**: `src/devops_cli/telemetry/instruments.py` shows that a counter only increases, so it cannot hold the current count of unchecked items or the age of the oldest check.
- **Use a summary instead of a histogram for searches per check.**: `docs/TELEMETRY.md` states that Prometheus stores each histogram as a native histogram and that dashboards read it with `histogram_quantile` and `histogram_count`. A summary computes quantiles in the client and does not aggregate across processes.
- **Use `absent()` on the search counter for the alert.**: `k8s/monitoring/prometheus-values.yaml` uses `absent()` only for a missing series, such as `ClusterMetricsMissing`. A counter that exists and does not increase is the real condition here, which `increase() == 0` states.
- **Depend on #2946, which makes the check search before it returns not-applicable.**: `openspec/changes/archive/2026-11-01-2946-the-alternatives-check-must-search-before/proposal.md` shows that change is already archived. The telemetry measures the check's behavior and needs no change to its logic.
