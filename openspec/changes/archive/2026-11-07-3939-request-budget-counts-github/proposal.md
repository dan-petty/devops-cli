# Proposal

## Why

Issue #3939: the roadmap Service sits at its budget of 2000 GitHub requests per hour all day, and its rounds start late or not at all. On 2026-11-07 the counter `devops_cli_github_requests_total{job="roadmap-service"}` showed 1,800 to 1,970 requests in each of the last 12 hours. The Service log held the warning "no round starts until the window has room" 66 times in 24 hours. In the last hour, 2020 requests: 887 with status 200, 880 with status 304 and 264 with no status (`none`).

GitHub does not count a conditional request that it answers with 304 against the primary rate limit. The budget protects that limit, and `RequestBudget.admit` counts a request before it is sent, so it counts each 304 answer. 44% of the budget goes to requests that GitHub does not count. The related item #3672 (an idle repository polls less often) cuts requests by a different way, and this change does not replace it.

## What Changes

- `GitHubRateLimiter` keeps a second hook beside the request gate: `set_request_gate(gate, refund)`. `count_request` calls `refund` once for an attempt with status 304.
- `RequestBudget.refund` takes the newest request out of the window, the budget file and the cost of a round. `ServiceManager.start` sets both hooks.
- A request with no answer stays in the budget. GitHub may have received it, and a gh command has no status to read (`none` is the status of every gh command).
- The metric `devops_cli_github_requests_total` stays as it is: it counts every attempt with its `status`. `devops_cli_service_budget_spent_requests` shows what the budget counts.
- The alert `RoadmapServiceGitHubRequestsHigh` sums the requests with `status!="304"`. Without that, it fires all day at 2020 requests while the budget is at 1140.
- The setting description of `service.github_requests_per_hour`, `docs/TELEMETRY.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md` and `k8s/README.md` say what the budget counts. The value of the budget does not change.
- The change alters what a service and an alert do, so it carries a spec delta.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-limits`: the budget counts what GitHub counts.
- `roadmap-service-alerts`: the alert of the request volume leaves out the answers with status 304.

## Impact

- `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/server/service.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/telemetry/instruments.py`.
- `k8s/monitoring/prometheus-values.yaml`, `tests/github/test_service_limits.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`.
- `docs/TELEMETRY.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `k8s/README.md`.
- Consequence for the cluster: the Service sends more requests than before for a while, because the rounds that waited can run. The requests that GitHub counts stay under the budget by the same gate as before.

## Feasibility

Read on 2026-11-07.

- **GitHub documents the rule:** "Best practices for using the REST API", section "Use conditional requests": a conditional request does not count against the primary rate limit if GitHub answers 304 and the request carries an `Authorization` header. The session always sends the token.
- **The limit that the budget protects:** "Rate limits for the REST API": the minimum limit of an installation is 5,000 requests per hour (up to 12,500 outside GitHub Enterprise Cloud). The budget of 2000 is the owner's setting, and this change keeps it.
- **The code counts 304:** `RequestBudget.admit` runs in `GitHubRateLimiter.acquire`, before the request is sent, so the status is not known there. `count_request` in `rate_limiter.py` is the one place that holds the status of each attempt of the session.
- **Prometheus, 1 hour at 2026-11-07:** by status 200 = 887, 304 = 880, none = 264, a total of 2020. By row, without 304: metrics 288, refine 286, other 236, implement 139, stage_ready 85, release_comments 46, stage 43, intake 16. After this change the budget would count about 1140.
- **Status `none`:** every row of it is a GET on the `core` resource. A gh command always counts with `none`, and a lost connection does too. The metric cannot tell the two apart, and a request that timed out may have reached GitHub, so these stay in the budget.

## Existing Tool Considered

The GitHub conditional request (#3497) and `RateLimit` parsing of `gidgethub` already exist. No library counts a local budget by status, so the change adds one hook and one method to the existing gate. Cost written as AGENTS.md rule 3 asks: about 60,000 tokens to build, a few thousand tokens a year to keep, one method and one condition to fix, and about 2 hours elapsed. It deletes no code.
