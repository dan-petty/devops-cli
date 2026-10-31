# Design

## Context

The roadmap Service runs two lanes per repository: the status lane and the model lane. Previously, any accepted webhook delivery queued a trigger on every lane worker, running full rounds of all due jobs. Issue #2009 added scoped intake updates to `src/devops_cli/roadmap/run.py`. This change connects the webhook receiver to those scoped updates through the lane workers.

## Decisions

- **Expose `issue` on `GitHubWebhookPayload`.** `GitHubWebhookPayload` reads `issue.number`. Pydantic ignores other issue fields through `extra="ignore"`.
- **Pass `payload` to `deliver`.** `_hand_to_consumers` passes `payload` to `consumer.deliver` when `deliver` accepts it. Existing consumers that only take three arguments continue to work without change.
- **Scope check in `roadmap_consumer`.** When `(event, action)` is in `SCOPED_UPDATES` and `payload.issue` is present, `roadmap_consumer` constructs `WebhookDelivery` and schedules `run_scoped_update` on the lane from `SCOPED_UPDATES` (`model` lane).
- **Run on the lane worker via `enqueue_scoped`.** `RepoWorker` gains a deque of scoped update callbacks. The worker thread executes scoped callbacks and coalesced batches sequentially, ensuring scoped updates never run concurrently with lane jobs.
- **No full round queued for scoped updates.** When a scoped update is enqueued, no trigger key is placed in `_pending_counts`. The status lane receives no trigger, and the model lane runs only the scoped update.
- **Fallback to whole-round hint.** When an event has no entry in `SCOPED_UPDATES` or lacks an issue number, `roadmap_consumer` calls `service_manager.enqueue_trigger` as before.

## Rejected Alternatives

- **Run scoped updates asynchronously outside `RepoWorker`**: rejected. Running outside `RepoWorker` would allow scoped intake to write `intake.json` while an intake job on the model lane is running.
- **Create a separate lane for scoped updates**: rejected by ADR 0017. A separate lane would race the model lane for the same repository.
- **Pass entire request or store through the router**: rejected. The router keeps clean separation from the roadmap store and jobs.

## Risks

- A slow scoped update could delay scheduled jobs on the model lane. Scoped intake only judges one issue and bounds model interaction time.
