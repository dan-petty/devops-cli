# Proposal: #6012

## Why
The hourly GitHub budget of the Service (`service.github_requests_per_hour`, 4000) holds rounds all day (#6012). In the 6 hours to 2026-11-16T19:40Z, `devops_cli_github_requests_total{job="roadmap-service"}` gave about 1440 counted requests an hour (status not 304) under the row `other`, 1135 under `metrics` and 536 under `refine`, and the budget held rounds 254 times. Nobody can tell which loop sends the requests of `other`, and the cluster cannot slow the `metrics` row without a release. #6012 is the first step: name the loop of each request and measure. The cache of #6013 and the events of #5555 and #4413 come next.

## What Changes
- The worker scope of a Service round names its loop: `poll` for a round of poll triggers, `webhook` for a round with a webhook delivery and for a scoped update. Each row keeps its own name.
- The read of the open work after a round counts under `idle_check`. Only the lane of `intake` sends it, in place of each of the 14 lanes.
- The new ast-grep rule `github-request-scope-row` refuses a `request_scope` call in `src/` that names no row.
- The new section `roadmap.metrics` holds `interval_minutes` (code default 13), which the `metrics` row reads at each round. The window of failed hook deliveries grows with it.
- `docs/CLUSTER.md` and `docs/TELEMETRY.md` name the loops; the generated settings documents list the new section.

The metric labels, the poll cadence and the cadence of the `metrics` row are observable behavior, so the change has spec deltas.

## Capabilities
- `github-api-metrics`: the row of the round's own reads, and the rule on each request scope.
- `roadmap-service-limits`: one lane reads the open work.
- `roadmap-row-cadence`: the interval of the `metrics` row.
- `roadmap-service-alerts`: the window of failed deliveries follows the interval.

## Impact
The Service only. The cut removes 13 of the 14 reads of the open work in each round of each repository: about 1220 counted requests an hour of 4000, from the measured `other` row of 7 repositories. The code default of the `metrics` interval stays 13 minutes, so that setting saves nothing until the ConfigMap sets it. The change fits one pull request.

## Feasibility
`request_labels()` (`src/devops_cli/github/request_scope.py`) gives the `row` label of each count in `session_transport._request` and in `run_gh`. Before the change, `ast-grep run -p 'request_scope($$$A)' src` found 9 calls of `request_scope`. The 2 calls with no row were the batch scope and the scoped scope of `RepoWorker` (`src/devops_cli/server/service.py`). After the change it finds 10 calls, and the new rule reports none. Prometheus showed no series with `repo="other"` in 24 hours, so every `other` request of the Service runs inside a worker, outside a row. Prometheus also showed 14 lanes for each repository (`devops_cli_service_queue_depth`) and 9.38 polls an hour for each repository (`devops_cli_service_triggers_total`). For a repository with one page of open issues, this agrees with 15 counted `other` requests for each poll: 14 reads of the open work and 1 read of the issue events.

## Existing Tool Considered
The row names are the project's own label of `devops_cli_github_requests_total`, so no library names them. ast-grep (`ast-grep-cli`, already in `pyproject.toml`, with its rules under `.ast-grep/rules/`) holds the source rule, so no checker code is written. The scope seam, the idle read and the cadence section exist; the change gives them a name, a lane and a setting. Written cost of the code kept: about 6,000 tokens and 3 hours to build, and about 1,000 tokens a month to keep. The change deletes the 13 redundant idle reads of each round and no module.
