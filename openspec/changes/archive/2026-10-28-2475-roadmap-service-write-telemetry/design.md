# Design

## Context

The roadmap Service runs one worker for each lane of each repository of `service.repos`. Every GitHub request of the process goes through `GitHubRateLimiter.acquire`, from `run_gh` and from the session, and `acquire` counts it in the OTLP counter `devops_cli_github_requests_total`. The Service's own state (jobs, triggers, deliveries, the identity refusal) is in its `prometheus_client` registry `GLOBAL_METRICS`, which Prometheus scrapes on `/metrics`. Both paths give the series `job="roadmap-service"` (#2472). Refine's selection reads the comments of an item whose wait it judges, `refine_one_item` reads them again before its model call, and every comment refine posts carries `CONST_ROADMAP_REFINE_COMMENT_MARKER`.

## Decisions

- **A context variable names the repository and the row.** `request_scope(repo=..., row=...)` sets a `ContextVar`, and `acquire` adds `request_labels()` to each count. `RepoWorker._execute_batch` enters the scope of its repository, and `_execute_due_rows` the scope of each row. The worker exists only for a repository of `service.repos`, and the rows come from the due table, so each label has a bounded set of values. The session's portal and `anyio.to_thread` copy the context of the sending thread, so a session request counts as a gh command does.
- **`method` is the HTTP method.** `run_gh` reads it from the `gh api` argv (`parse_gh_api_args`), and the session passes its own. GraphQL is a POST for a read and a mutation alike. gh chooses the requests of its other commands, so such a command counts as POST when it writes and GET when it reads, as `is_write_gh_command` classifies it.
- **The write alert counts REST requests that are not a GET.** The roadmap jobs write only through REST, and their GraphQL documents are queries, so `method!="GET", resource!="graphql"` counts each write and no read.
- **The budget and the suspensions are `/metrics` gauges.** A gauge on the OTLP path has a sample only in an interval in which it was set (delta temporality). The Service's registry is scraped at each interval, and it holds the other `devops_cli_service_*` series. The budget publishes its limit at start and the requests of its window at each round and each check, and counts a hold when it begins, where it logs it. The ledger publishes 1 or 0 for each job it records, at start too, so a kept suspension shows after a restart.
- **The self outcome maps the refusal status.** The router keeps the consumer's refusal status as the answer and maps `ignored_own_write` to the outcome `self`; any other refusal stays `ignored`. The roadmap consumer is defined in the router's module, so the map holds no outside name.
- **Firecrawl counts at its one call site.** `firecrawl_search` is the only caller of the Firecrawl API. It counts `ok`, the HTTP status of a refusal, or `error`, and logs one warning with the status or the error class. The query and the key are in the request body and header, and the warning names neither. `search_web` still answers the model with the failure.
- **Selection applies the cap.** `_Selection.consider` reads the comments of an item whose wait is over, once for the selection, counts refine's marked comments of the last 24 hours, and at the cap leaves the item waiting on a person. The item takes no place under `--limit`, so items at the cap never hold the round back from the other items, and the round makes no model call for it. `--item` does not go through the selection, so a person can refine the item at the cap.
- **The record makes each stop count once.** The cap stops the comment that would answer the item's newest comment. A round that leaves the item alone for a newest comment that the job record does not hold carries the stop in its plan. `apply_refine` then records that comment's creation time as `refine.capped_after`, logs one warning and adds 1 to the counter. A later round that finds the same newest comment leaves the item alone again with no write, no warning and no count, so the counter follows the comments the cap stopped and not the rounds. A newer comment is a new comment that refine would answer, and counts once.

## Rejected Alternatives

- **Repo from the request path.** A REST path names its repository, but a GraphQL request carries it in its variables, and the row cannot come from a path at all. The scope gives both from one place.
- **A `job` label.** Prometheus gives each scraped series the label `job`, so the label is `row`.
- **OTLP gauges for the budget.** Rejected for the sparse samples above: an alert or a panel would see the gauge only in the minutes after a round set it.
- **A Loki ruler for the log lines.** It needs a ruler deployment and a second rule language, and the log lines carry no labels to group by.
- **A cap in the store's comment path.** The store does not know which comments are refine's, and a cap there would not stop the model call of each round.
- **A cap that counts the bot's comments by author.** `IssueComment` holds no author, and an author is not refine's alone: a person can run refine. The marker already tells refine's comments apart, and refine reads them with no other request.
- **The cap in `refine_one_item`, after the selection.** An item at the cap took one of the `--limit` places in every round: with another bot's reply after each refine comment, `_still_waiting` ended its wait at each round, and three such items kept refine from every other item for up to 24 hours. Each round also counted and logged the same stopped comment again, so the counter grew with the rounds (review of the pull request, reproduced with three items at the cap and one other item over two rounds).
- **A count at each round with no record.** Without a record, a round cannot tell a newest comment that an earlier round already left with no answer from a new one. The record is one write for each new comment on an item at the cap, which another actor's comment causes, and never a comment, so it gives another bot nothing to answer.
- **A count kept in the Service process.** `devops roadmap refine --confirm` runs outside the Service, and a restart would lose the count, so a stop would count again.
- **A cap of 3 comments.** The go-live watch stops at more than 2 bot comments on one issue in 24 hours. With 2, refine can ask and answer once a day, and a loop stops after two comments.

## Risks

- An item whose person replies fast waits until the oldest of refine's two comments is 24 hours old. The plan names the reason, and the README says so.
- Another actor that comments each time the Service edits an issue would get one record write from each round on an item at the cap. Refine runs once an hour, and each of these writes counts, so the counter shows such a loop.
