# Proposal

## Why

Issue #814: no dashboard shows how many requests devops-cli sends to GitHub, how often GitHub refuses them, or how many GraphQL points they cost.

- The rate limiter paces each request. It counts the requests, the throttles and the throttle wait in the quota ledger of the identity (`src/devops_cli/github/rate_limiter.py`). Only `devops gh rate-limit` reads these totals, and no metric sends them.
- A count of requests does not show the GraphQL cost. On 2026-10-07, about 300 gh calls spent about 4,850 points in one window. A quiet hour sent 158 calls for about 158 points (comment on #814, 2026-10-08).

## What Changes

- The new counter `devops_cli_github_requests_total`, by `resource`. The rate limiter adds 1 for each attempt that it paces: a gh command or a request of the GitHub session, and each retry. The resource is the rate-limit resource that the request spends, such as `core`, `graphql` or `search`.
- The new histogram `devops_cli_github_throttle_wait_seconds`, by `resource`. Each throttle adds one observation: the seconds that devops-cli waits before it sends the refused request again. The count of the histogram is the count of throttles.
- The new counter `devops_cli_github_graphql_points_total`. It adds the cost that each GraphQL answer reports in `rateLimit.cost`.
- `GitHubRateLimiter.record_throttle` takes the resource of the request that GitHub refused.
- The new row "GitHub API" in `k8s/monitoring/dashboards/devops-cli.json` shows the requests by resource, the throttles and their wait by resource, and the GraphQL points.
- `docs/TELEMETRY.md` lists the three metrics. `devops docs generate` writes the list from `INSTRUMENTS`.
- A consumer sees the metrics and the dashboard, so the change has a spec delta: the new capability `github-api-metrics`.
- This change fits one pull request.

The change does not build these parts of the 2026-10-08 update of #814:

- The gauge of the GraphQL points left and the spend by repository of each Service round. Both come from the GraphQL budget read of the board store (`GitHubRoadmapStore.graphql_spend`, `src/devops_cli/roadmap/board_read.py`). #2399 moves the roadmap state to labels and milestones, and no roadmap job reads or writes the board after it. The board reads were the GraphQL cost of the Service. `devops_cli_github_graphql_points_total` counts the GraphQL cost of every process, the Service included.
- The gauge `devops_cli_service_paused_until_seconds`. The Service pauses only after a GraphQL budget refusal (`service_pause_until` in `src/devops_cli/roadmap/run.py`). The Service does not run now (`replicas: 0`, #1562), and #1647 and #2399 change its identity and its GraphQL use.

## Capabilities

### New Capabilities

- `github-api-metrics`: the metrics that devops-cli sends about its requests to GitHub, and the dashboard row that shows them.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/github/session_transport.py`.
- `k8s/monitoring/dashboards/devops-cli.json`.
- `tests/test_github_api_metrics.py`, `tests/test_telemetry_instruments.py`, `tests/test_github_rate_limiter.py`.
- `docs/TELEMETRY.md`, which `devops docs generate --sync-readme` rewrites.

## Feasibility

Checked on origin/main bb46660c on 2026-10-28.

- One place sees each request. `run_gh` paces each attempt with `GitHubRateLimiter.acquire` (`_execute_gh_single_attempt`). The GitHub session paces each attempt with the same method (`pace_request` in `src/devops_cli/github/session_transport.py`). The `/rate_limit` read is not paced, and GitHub does not charge it.
- One place sees each throttle. `_handle_attempt_backoff` (`run_gh`) and `retry_wait` (the GitHub session) call `record_throttle` with the wait, and both know the resource of the request.
- One place sees each GraphQL cost. `_extract_graphql_ratelimit_json` calls `charge_points("graphql", cost)` for each answer that holds `rateLimit.cost`.
- `INSTRUMENTS` has counters and histograms, and `emit()` sends them as OTLP deltas (`src/devops_cli/telemetry/instruments.py`). Prometheus 3 stores a histogram as a native histogram, and `histogram_count` and `histogram_sum` read it.
- `tests/test_telemetry_instruments.py` lets a dashboard query only the series in `INSTRUMENTS`. A Service gauge on the Prometheus endpoint of the Service (`GLOBAL_METRICS`) cannot be on the dashboard.
- #1647 changes the identity plumbing of the rate limiter and the session transport (`token` becomes `identity`). It does not change `acquire`, `record_throttle` or `charge_points`.

## Existing Tool Considered

The change uses the OpenTelemetry SDK through `emit()`, which devops-cli already uses for every metric. GitHub gives no metric of the requests of one client: `GET /rate_limit` gives only the quota that is left for each resource. `opentelemetry-instrumentation-httpx` would count the requests of the GitHub session, but not the gh commands that `run_gh` starts, and it does not know the rate-limit resource or the throttle wait. The change builds no new code path: it adds three `emit()` calls where the rate limiter already counts. It deletes no code.
