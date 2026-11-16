# Design

## Decisions

### The worker scope names the loop of the round
`RepoWorker._execute_batch` opens `request_scope(repo=..., row=round_loop(batch.counts))`. `round_loop` gives `webhook` when a trigger of the batch is not a poll, else `poll`, so a poll that a webhook joins counts as `webhook`. `_execute_scoped` names `webhook`, because only a webhook delivery enqueues a scoped update. `_execute_due_rows` still opens `request_scope(row=row.name)` for each row, so a row keeps its own name. The Service already labels its trigger counter with the same two sources (`CONST_SERVICE_SOURCE_POLL`, `CONST_SERVICE_SOURCE_WEBHOOK`), so the label set stays bounded.

### The read of the open work has its own name and one lane
`service_job` reads `repository_is_idle(store)` in `request_scope(row="idle_check")`. The read sets only the poll interval of the repository (#3672), and every lane of a repository runs a round for each trigger. So `service_jobs` gives `idle` only to the lane that holds `intake`. Measured: 14 lanes for each repository, each sent this read after each round. That is 131 of the 141 counted `other` requests an hour of a repository with one page of open issues.

### The metrics row reads its interval from a setting
`RoadmapMetricsConfig(RowCadenceConfig)` holds `interval_minutes` with the default `DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES` (13), and the `metrics` row has `cadence=attrgetter("metrics")`, as the other cadence rows have. The row gives no queue, so the backlog rule never applies. The rows `github_status` and `cloudflare_status` keep a fixed 13 minutes in `DEFAULT_ROADMAP_STATUS_PAGE_INTERVAL_MINUTES`, because they send no GitHub request. A module outside `config/` must not read the default of a setting (`tests/invariants/test_source_tree.py`), so they cannot keep the metrics default.

### The window of failed deliveries grows with the interval
The default window of 15 minutes is 2 minutes longer than the default interval, so each delivery is in at least one read (#5017). `delivery_window_minutes(interval)` keeps that margin in `DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MARGIN_MINUTES`: it gives `max(15, interval + 2)`, so a slower row still reads each delivery.

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
