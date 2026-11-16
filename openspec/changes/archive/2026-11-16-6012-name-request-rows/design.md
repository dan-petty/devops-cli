# Design

## Decisions

### The worker scope names the loop of the round
`RepoWorker._execute_batch` opens `request_scope(repo=..., row=round_loop(batch.counts))`. `round_loop` gives `webhook` when a trigger of the batch is not a poll, else `poll`, so a poll that a webhook joins counts as `webhook`. `_execute_scoped` names `webhook`, because only a webhook delivery enqueues a scoped update. `_execute_due_rows` still opens `request_scope(row=row.name)` for each row, so a row keeps its own name. The Service already labels its trigger counter with the same two sources (`CONST_SERVICE_SOURCE_POLL`, `CONST_SERVICE_SOURCE_WEBHOOK`), so the label set stays bounded.

### The read of the open work has its own name and one lane
`service_job` reads `repository_is_idle(store)` in `request_scope(row="idle_check")`. The read sets only the poll interval of the repository (#3672), and every lane of a repository runs a round for each trigger. So `service_jobs` gives `idle` only to the lane that holds `intake`. Measured: 14 lanes for each repository, each sent this read after each round. That is 131 of the 141 counted `other` requests an hour of a repository with one page of open issues.

### The metrics row reads its interval from a setting
`RoadmapMetricsConfig(RowIntervalConfig)` holds only `interval_minutes` with the default `DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES` (13), and the `metrics` row has `cadence=attrgetter("metrics")`, as the other cadence rows have. `RowIntervalConfig` is the new base of `RowCadenceConfig`: it holds the interval with no backlog rule, because the row counts no queue and a backlog setting would do nothing. `_Cadences` reads a section of either kind. The rows `github_status` and `cloudflare_status` keep a fixed 13 minutes in `DEFAULT_ROADMAP_STATUS_PAGE_INTERVAL_MINUTES`, because they send no GitHub request. A module outside `config/` must not read the default of a setting (`tests/invariants/test_source_tree.py`), so they cannot keep the metrics default.

### The read of failed deliveries starts at the last good read
The row runs when a trigger comes after its interval, so the time between two reads is the interval and the wait for the next trigger: 151 s by default, about 384 s live, and 600 s for an idle repository. A fixed window of 15 minutes left up to about 8 minutes unread at the default interval, and one page of 100 deliveries held only 22 minutes of devops-cli. So `report_delivery_failures` keeps the time of the last good read of each repository beside `_set_codes`, and a read counts from that time, or from 15 minutes before the read when that is earlier, so the gauge still holds at least 15 minutes for the alert. The read asks GitHub for the failed deliveries only (`status=failure`), so a page holds a longer time, and it follows the `Link` of each page until a delivery is older than its start. A failed read keeps the start. A read reads at most `DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES` (10) pages of a hook and logs a warning, so a long stop of the row costs a bounded number of requests. A new process starts at the window: the time of the last read is not kept across a restart.

### A source rule and a contract test
The ast-grep rule `github-request-scope-row` fails on a `request_scope` call in `src/` with no `row=` argument. A contract test runs every lane that `service_jobs` builds in the workers of the Service over the repository fake, with each row of the table stubbed to read one issue. It records the `row` of each request at the runner and at `session_transport.count_request`, and fails when one is `other`.

## Rejected alternatives

- Infer the row from the call stack. A stack guess fails when a helper sends the request, and it hides a new loop. The context variable of `request_scope` already reaches every count (`request_labels()` in `session_transport._request` and `run_gh`).
- Name the round's own reads after the lane. A default lane has the name of its row (`service_lanes`), so the reads of the `metrics` lane would count as the `metrics` row, and the two loops would look the same.
- One name, such as `reconcile`, for the round's own reads. It hides whether a poll or a webhook sent them, which the measurement of #6012 must show.
- A run-time error when a request has no row. It stops the Service for a defect that the source rule and the test catch first.
- Keep the read of the open work in each lane and only rename it. The 13 extra reads give the same answer in the same round. From the measured counts, they cost about 1220 counted requests an hour.
- Answer a single-page listing with `If-None-Match`. The transport keeps no page that links no next page (`session_transport`), because a 304 carries no `Link`. A cut there changes a rule of the session for every caller; the Service refunds 304 answers already, so the cache of #6013 is the place for it.
- Keep the label times of the `metrics` row across restarts. That is a cache of GitHub data, which #6013 builds.
- Make the window of failed deliveries the metrics interval plus 2 minutes. The row runs only when a trigger comes after its interval, so the gap between two reads is longer than the interval, and one page of 100 deliveries held 22 minutes of devops-cli: deliveries were still lost.
- Read the deliveries through the GitHub session, whose `paginate` follows the `Link`. The metrics row reads its other GitHub sources through gh, and 7 tests of the row fake gh at the process edge. Two of them run as the GitHub App, whose session mints a token with a private key that the tests do not hold, so each test would need a new fake of the API and of the token.
- Keep a 2xx delivery in the listing. `status=failure` gives the same count with fewer pages.
