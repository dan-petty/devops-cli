# Design

## Context

The roadmap Service runs one worker for each lane of each repository of `service.repos`. Every GitHub request of the process goes through `GitHubRateLimiter.acquire`, from `run_gh` and from the session, and `acquire` counts it in the OTLP counter `devops_cli_github_requests_total`. The Service's own state (jobs, triggers, deliveries, the identity refusal) is in its `prometheus_client` registry `GLOBAL_METRICS`, which Prometheus scrapes on `/metrics`. Both paths give the series `job="roadmap-service"` (#2472). Refine reads an item's comments in `refine_one_item` before its model call, and every comment it posts carries `CONST_ROADMAP_REFINE_COMMENT_MARKER`.

## Decisions

- **A context variable names the repository and the row.** `request_scope(repo=..., row=...)` sets a `ContextVar`, and `acquire` adds `request_labels()` to each count. `RepoWorker._execute_batch` enters the scope of its repository, and `_execute_due_rows` the scope of each row. The worker exists only for a repository of `service.repos`, and the rows come from the due table, so each label has a bounded set of values. The session's portal and `anyio.to_thread` copy the context of the sending thread, so a session request counts as a gh command does.
- **`method` is the HTTP method.** `run_gh` reads it from the `gh api` argv (`parse_gh_api_args`), and the session passes its own. GraphQL is a POST for a read and a mutation alike. gh chooses the requests of its other commands, so such a command counts as POST when it writes and GET when it reads, as `is_write_gh_command` classifies it.
- **The write alert counts REST requests that are not a GET.** The roadmap jobs write only through REST, and their GraphQL documents are queries, so `method!="GET", resource!="graphql"` counts each write and no read.
- **The budget and the suspensions are `/metrics` gauges.** A gauge on the OTLP path has a sample only in an interval in which it was set (delta temporality). The Service's registry is scraped at each interval, and it holds the other `devops_cli_service_*` series. The budget publishes its limit at start and the requests of its window at each round and each check, and counts a hold when it begins, where it logs it. The ledger publishes 1 or 0 for each job it records, at start too, so a kept suspension shows after a restart.
- **The self outcome maps the refusal status.** The router keeps the consumer's refusal status as the answer and maps `ignored_own_write` to the outcome `self`; any other refusal stays `ignored`. The roadmap consumer is defined in the router's module, so the map holds no outside name.
- **Firecrawl counts at its one call site.** `firecrawl_search` is the only caller of the Firecrawl API. It counts `ok`, the HTTP status of a refusal, or `error`, and logs one warning with the status or the error class. The query and the key are in the request body and header, and the warning names neither. `search_web` still answers the model with the failure.
- **The cap leaves the item alone before the model call.** `refine_one_item` reads the item's comments before its model call already. It now reads them first, counts refine's marked comments of the last 24 hours, and at the cap returns a skipped item that waits on a person, with no model call and no write. A cap at the comment write would let the round call the model each time, and the reply that the cap left unanswered would select the item again at the next round.

## Rejected Alternatives

- **Repo from the request path.** A REST path names its repository, but a GraphQL request carries it in its variables, and the row cannot come from a path at all. The scope gives both from one place.
- **A `job` label.** Prometheus gives each scraped series the label `job`, so the label is `row`.
- **OTLP gauges for the budget.** Rejected for the sparse samples above: an alert or a panel would see the gauge only in the minutes after a round set it.
- **A Loki ruler for the log lines.** It needs a ruler deployment and a second rule language, and the log lines carry no labels to group by.
- **A cap in the store's comment path.** The store does not know which comments are refine's, and a cap there would not stop the model call of each round.
- **A cap that counts the bot's comments by author.** `IssueComment` holds no author, and an author is not refine's alone: a person can run refine. The marker already tells refine's comments apart, and refine reads them with no other request.
- **A cap of 3 comments.** The go-live watch stops at more than 2 bot comments on one issue in 24 hours. With 2, refine can ask and answer once a day, and a loop stops after two comments.

## Risks

- An item whose person replies fast waits until the oldest of refine's two comments is 24 hours old. The plan names the reason, and the README says so.
- A round that the cap stops counts again at each later round while a reply waits, so the counter grows with the rounds, not with the comments that would have been written. Each count is still a comment that the round did not write.
