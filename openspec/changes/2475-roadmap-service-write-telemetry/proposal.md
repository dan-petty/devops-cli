# Proposal

## Why

Issue #2475: a go-live review of the roadmap Service found that its riskiest behavior has no metric and no cap.

- `devops_cli_github_requests_total` carries only `resource` (`src/devops_cli/github/rate_limiter.py`, `GitHubRateLimiter.acquire`). A burst of comments or label writes, or a refine comment loop, shows only on GitHub, and the alert `RoadmapServiceGitHubRequestsHigh` cannot tell the operator which repository spent the budget.
- No cap limits refine's comments on one item.
- A budget hold and a job suspension show only in the log (`RequestBudget.holds` in `src/devops_cli/server/service.py`, `_count_failure` in `src/devops_cli/roadmap/run.py`), and Loki has no ruler.
- The webhook self-filter shares the outcome `ignored` with the other ignored deliveries (`_hand_to_consumers` in `src/devops_cli/server/routes/webhooks.py`), so an echo loop with another bot does not show.
- Firecrawl searches have no metric, and a failed search (401, 402, 429) logs nothing (`firecrawl_search` in `src/devops_cli/ai/common_tools.py`, `InvestigationTools.search_web` in `src/devops_cli/roadmap/refine_investigation.py`).

## What Changes

- `devops_cli_github_requests_total` gets the labels `method`, `repo` and `row`. `method` is the HTTP method; a GraphQL request is a POST, and a gh command other than `gh api` is a POST when it writes and a GET when it reads. A worker of the Service runs its rounds in the request scope of its repository, one of `service.repos`, and a round runs each job row in the scope of its name (`metrics`, `intake`, `refine`). A request outside a worker or a row counts as `other`. The label is `row`, not `job`, which is the scrape label of Prometheus. A context variable carries the scope, and anyio copies it into the thread of the session's portal, so a request of the session counts as a gh command does.
- The Service's `/metrics` shows `devops_cli_service_budget_limit_requests`, `devops_cli_service_budget_spent_requests`, `devops_cli_service_budget_holds_total` (one count each time a hold begins) and `devops_cli_service_job_suspended` (1 while a job waits for new input after it failed its limit of rounds, by `repo` and `row`).
- A delivery of the App bot's own write counts as outcome `self` in `devops_cli_service_webhook_deliveries_total`. Its answer stays HTTP 200 with status `ignored_own_write`.
- `firecrawl_search` counts each search in `devops_cli_firecrawl_searches_total` by `result`: `ok`, the HTTP status of a refused search, or `error`. A failed search logs one warning that names the status or the error class, never the key or the query.
- A refine round leaves an item alone when refine wrote `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` (2) comments on it in the last `CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS` (24) hours: no model call and no comment. The item waits on a person, with the reason in the plan, and takes no place under `--limit`. For each newest comment on the item that the cap leaves with no answer, `--confirm` records its time in the job record (`refine.capped_after`), logs one warning and adds 1 to `devops_cli_roadmap_refine_comments_capped_total`; a later round with no newer comment does none of these. `--item` refines an item at the cap, since a person asked for it.
- The new rule group `roadmap-service-activity` holds `RoadmapServiceGitHubWritesHigh` (more than 300 GitHub writes in 1 hour), `RoadmapServiceSelfDeliveriesHigh` (more than 150 deliveries of the Service's own writes in 1 hour) and `RoadmapServiceFirecrawlRefused` (any Firecrawl 402 or 429 in 1 hour). It is apart from the groups of #2472 and #2476. `k8s/README.md` says what to do for each alert, and where the new series are.
- The OTLP instruments are declared in `src/devops_cli/telemetry/instruments.py`, and `docs/TELEMETRY.md` is generated from them. The Service's `/metrics` series are declared beside the other `devops_cli_service_*` names in `src/devops_cli/config/constants.py`, as the instrument check allows for `GLOBAL_METRICS`.
- The change alters what the Service counts, logs and writes, and what alerts fire, so it carries spec deltas in `github-api-metrics`, `roadmap-service-limits`, `github-app-identity`, `roadmap-service-alerts` and `roadmap-refine`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `github-api-metrics`: each request names its method, repository and job row.
- `roadmap-service-limits`: the budget, its holds and the suspended jobs show on `/metrics`.
- `github-app-identity`: the App bot's own write counts as outcome `self`.
- `roadmap-service-alerts`: the group `roadmap-service-activity` and its three alerts.
- `roadmap-refine`: the cap on refine's comments on one item, and the count of each Firecrawl search.

## Impact

- `src/devops_cli/github/request_scope.py` (new), `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/github/session_transport.py`, `src/devops_cli/server/service.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/ai/common_tools.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- `tests/test_github_api_metrics.py`, `tests/test_service_limits.py`, `tests/test_server_service.py`, `tests/test_common_tools.py`, `tests/test_roadmap_refine.py`, `tests/test_roadmap_dry_runs.py`, `tests/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`.
- `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`, `docs/TELEMETRY.md`, and the generated help of `devops roadmap refine`.

## Feasibility

- Each line that the issue names was read on `origin/main` 2d38f8d8. `GitHubRateLimiter.acquire` emits `GITHUB_REQUESTS_TOTAL` with `{"resource": target}` only. `RequestBudget.holds` logs `budget_spent` and counts nothing. `_count_failure` logs `job_suspended` and counts nothing. `_hand_to_consumers` answers every refusal with outcome `ignored`. `firecrawl_search` has no `emit`, and `search_web` turns an `httpx2.HTTPError` into a tool answer with no log line. `apply_refine` posts `reason_comment` with no count of earlier comments.
- The session paces each request in `anyio.to_thread.run_sync` inside a task of its blocking portal. anyio 4.15.1 starts the portal's task through `loop.call_soon_threadsafe`, whose handle copies the context of the calling thread, and `to_thread.run_sync` runs the function in `context.run` (`anyio/_backends/_asyncio.py`). The new test `test_a_session_request_counts_the_scope_of_the_thread_that_sent_it` shows the scope of the sending thread on the session's count.
- The OpenTelemetry SDK 1.x last-value aggregation drops its value after each collection with delta temporality (`_LastValueAggregation.collect` in `opentelemetry/sdk/metrics/_internal/aggregation.py`), and devops-cli exports deltas. An OTLP gauge then has a sample only in the intervals in which it was set. So the budget and suspension gauges are on the Service's `/metrics`, which Prometheus scrapes at each interval, beside the other `devops_cli_service_*` series.
- Firecrawl's error catalog (<https://docs.firecrawl.dev/api-reference/errors>, read 2026-10-28) gives 401 "Unauthorized: Invalid token", 402 "Payment Required: Insufficient credits" and 429 "Rate limit exceeded" or "Concurrency limit reached"; its rate-limit page says that "exceeding either returns a `429` response".
- The Service writes only through REST: the roadmap store sends its comments, labels, issue edits and issue creations as `gh api -X POST|PATCH`, and its GraphQL documents are queries (`repository_query_args`). So a write alert over REST requests that are not a GET counts every write of the roadmap jobs.
- The pinned promtool 3.15.0 (`tools.lock`) accepts the new group and passes its unit tests.

## Existing Tool Considered

The change uses what the project already has: the declared OTLP instruments and `emit()`, the Service's `prometheus_client` registry, the kube-prometheus-stack rule files with promtool's unit tests, and Python's `contextvars`, which anyio and asyncio copy across threads and tasks. A Loki ruler for the log lines was the other option in the review; it would need a new ruler deployment and a second rule language for the same signals, while the counters cost one line at each site. Nothing new is built, and the change deletes no internal code. The cap reads the comments in the selection, once for each item whose wait it judges, and `_still_waiting` reads the same list, so an item at the cap costs no other request.
