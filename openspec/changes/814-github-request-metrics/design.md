# Design

## Decisions

- **The rate limiter sends the metrics.** `acquire`, `record_throttle` and `charge_points` are the one place where `run_gh` and the GitHub session meet. Each method sends its metric after its own update and outside its lock, so a slow export does not hold the pacing of another thread.
- **A request is counted when the rate limiter lets it go.** `acquire` sends the count after it calculates the wait and before it sleeps. An attempt whose quota the rate limiter cannot read raises before the count, because it is not sent.
- **The label is the rate-limit resource.** `core`, `graphql`, `search`, `code_search` and `code_scanning_autofix` are the resources that the rate limiter knows, so the label has few values. The command and the repository are not labels: the rate limiter does not know them, and the GitHub quota is per identity, not per repository.
- **One histogram for the throttles.** A native histogram holds the count and the sum of its observations. `histogram_count` gives the throttles, and `histogram_sum` gives the seconds of wait.
- **The session's 5xx retries are in the histogram.** `retry_wait` already records the wait before it sends a read again after a 5xx as a throttle in the ledger. The metric keeps the meaning of the ledger, and the description of the instrument says so.
- **The GraphQL points are one counter with no label.** All GraphQL points go to the `graphql` resource, so a resource label has one value.

## Rejected alternatives

- **A counter `devops_cli_github_throttles_total` next to the histogram.** It always agrees with `histogram_count` of the histogram, so the second series adds no data.
- **A gauge of the quota that is left, from each process.** Many short-lived processes of two identities (the gh login of a person and the identity of the Service) would write one series. Without a label for the identity, the series mixes two quotas. The key of the identity is a digest of its token or installation, which a dashboard cannot name. `devops gh rate-limit` shows the quota of the current identity.
- **The Service gauges on the Prometheus endpoint of the Service.** `tests/test_telemetry_instruments.py` lets a dashboard query only the series in `INSTRUMENTS`, and `test_no_gauge_reaches_prometheus_through_two_paths` refuses one gauge on two paths. The Service does not run now (`replicas: 0`), and #1647 and #2399 change its identity and its GraphQL use. The proposal names the parts that the change does not build.
- **`opentelemetry-instrumentation-httpx`.** It sees only the GitHub session. The gh commands that `run_gh` starts are child processes, and the instrumentation does not know the rate-limit resource or the wait.
