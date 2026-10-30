# Design

## Decisions

- **The row moves, and only the row.** `implement` leaves `MODEL_LANE_ROWS` and joins `STATUS_LANE_ROWS` after `metrics`. The lane runs `metrics` first, because it takes seconds and a person reads the gauges. `implement` follows. Its interval (10 minutes), its first-run rule and its clone rule (`needs_clone`) stay. It has no batch key, no due rule and no cross-job rule, so none moves. A trigger goes to every lane of the repository (`ServiceManager.enqueue_trigger`), so a poll reaches the status lane and the row is due there by its interval, with no wait for a model-lane round. The webhook events that make a round due (`issues` opened and reopened) are intake's hints: they made `implement` due before the move no more than they do now.
- **The lane label follows the worker.** `lane` on `devops_cli_service_jobs_total`, `devops_cli_service_job_seconds`, the queue depth and the start gauge is set by `RepoWorker`, not by the row. After the move the rounds of the row count under `lane="status"` with no code. The label `row` of `devops_cli_github_requests_total` and of `devops_cli_service_job_suspended` names the row and stays `implement`.
- **The ledger needs no migration.** `FailureLedger` keys an entry by `(repo, job)`. The record `service-failures.json` is a list of `[repo, job, rounds, failed_on]`. No field names a lane, so a record written before the move loads as it is, and a suspended `implement` row stays suspended on its new lane. `read_state_record` is not changed. A test loads a record with an `implement` entry into the ledger of the status lane.
- **The order inside the table.** `DEFAULT_DUE_TABLE` stays `(*STATUS_LANE_ROWS, *MODEL_LANE_ROWS)`. `devops roadmap run` now runs `metrics, implement, intake, refine, stage, alternatives`. An item that `stage` stages in the round gets its Job at the next round of the row, at most 10 minutes later. The Service never ran the two together, because its lanes are independent.

## The proof that no write loses a key

Claim: in one process, no write of the job record loses a key that another write set, whichever two lanes write.

The writers. Every write of the record of an issue goes through three methods of `GitHubRoadmapStore`: `set_field` (a field and its marks), `set_marks`, and `write_issue_body`. Each runs `with _JOB_RECORD_LOCK:` from its `GET` of the issue to the end of its `PATCH`. The `PATCH` body is `encode_job_record(held, changes)`: the record `held` that the `GET` returned inside the lock, with only the keys of `changes` set or cleared. The other writes of an issue (`close`, `label_issue`, `comment`, `create_issue`) send no body with a record block.

The lock is shared. `_JOB_RECORD_LOCK` is a module variable. `service_job` opens a store for each round, and both lanes are threads of the Service process, so every store of the Service takes the same lock.

The argument. Let W1 and W2 be two writes. The lock orders them. Say W1 comes first. `_write` returns when `gh` exits, so the `PATCH` of W1 has been answered before W1 releases the lock. W2 reads the issue after it takes the lock, so what it reads holds the keys of W1, and its `PATCH` keeps them. W2 changes only the keys it names. The families `refine.*`, `stage.*`, `alternatives.*` and `implement.*` have one writer each, and the field keys (`Status`, `Priority`, `Value`, `Effort`) are guarded by `require_unchanged` (ADR 0002), which raises when a field changed since the store read it. So no key is lost, and none is reverted without a raise.

What the lock does not cover. A writer outside the process: the runner Job (`devops roadmap implement`, a separate pod), a person's edit, and a `devops` command run by hand. GitHub has no conditional write of an issue (see Feasibility), so no `If-Match` or `updated_at` check can close the window between the `GET` and the `PATCH`. The move does not widen it: the Service's `implement` row writes only when it creates a Job (`implement.job`, before the Job exists) and when it reports a Job that ended (after the runner pod exited). So the row and the runner never write one item together. Before the move the model lane wrote in the same two windows.

Stale plans are safe. The row plans from the listing its store read at the start of the round. A model-lane write after that read can only make the plan late: `stage` sets an item Staged after the plan, and the next round takes it. If `stage` removes the `stage.*` keys of an item while the row creates its Job, the Job runs `roadmap implement --item N`, finds the item not eligible and ends. The row then records the state `succeeded` and nothing is lost.

The tests. `tests/test_roadmap_github_store.py` already holds a test for two mark writes. The change adds two tests that run the mixes the move creates, with two stores on one fake issue and a pause between the read and the write of the first writer: a field write with refine marks against a mark write of `implement.job`, and a body write against a mark write. Without the lock both lose a key, which the author checked by taking the lock out in a scratch copy.

## Rejected alternatives

- **A conditional write (`If-Match` or `updated_at`).** The docs of GitHub list conditional requests for `GET` only, and the endpoint "Update an issue" lists no precondition header or field. A check of `updated_at` before the `PATCH` is a second read, and so a smaller window and not a closed one. It would cost one more request per write for nothing the lock does not give in one process.
- **A second lock for the implement keys.** The one lock already covers every key of the record. Two locks would let the writes of one issue interleave.
- **Give the row its own third lane.** A new lane needs a new worker, clone, gauge series and alert series for one row that runs for seconds. The status lane has the same properties (no model call, short rounds).
- **Run `implement` first on the status lane.** `metrics` takes seconds and reads only. A failed Kubernetes call in `implement` should not hold the gauges back.
- **An explicit order for `devops roadmap run` that keeps `implement` after `stage`.** It needs a second source of order beside the two lane tuples. The CLI round is a development tool, and the row runs again in 10 minutes.
- **Add batch keys so a webhook makes the row due.** The Service takes only the `issues` events, and a comment `implement: retry` is an `issue_comment` event. Subscribing to it is a new feature with its own scoped update (ADR 0017), and not part of this item.
