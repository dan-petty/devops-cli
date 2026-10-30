# Proposal

## Why

Issue #1533, the second part after #2009: the roadmap Service treats every webhook delivery as a hint to run a full round of all due jobs across both lanes. No payload reaches any job. This wastes GraphQL budget and delays issue processing. The fix makes each subscribed webhook event run its scoped update at once on the lane that `SCOPED_UPDATES` names. The 5-minute poll reconciles board edits and lost deliveries.

## What Changes

- Add `WebhookIssue` to `src/devops_cli/models/webhooks.py` and add `issue: WebhookIssue | None = None` to `GitHubWebhookPayload`.
- Update `_hand_to_consumers` in `src/devops_cli/server/routes/webhooks.py` to pass the typed `payload` to `consumer.deliver` when accepted.
- Update `roadmap_consumer` in `src/devops_cli/server/routes/webhooks.py`:
  - When the delivery has an issue number and matches an entry in `SCOPED_UPDATES`, run the scoped update on the lane that the table names through `ServiceManager.enqueue_scoped`.
  - When the delivery cannot be scoped, enqueue a trigger on all lanes as a whole-round hint as before.
- Update `RepoWorker` and `ServiceManager` in `src/devops_cli/server/service.py`:
  - Add `enqueue_scoped` to dispatch a scoped update callable to the lane worker.
  - The lane worker executes the scoped update sequentially, records metrics and spans, and queues no full round.
- Update documentation in `k8s/README.md` and `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md` to describe the event-driven dispatch flow.

## Capabilities

### Modified Capabilities

- `roadmap-scoped-updates`: the Service hands each subscribed webhook event that carries an issue number to its scoped update on the lane the table names, queueing no full round.

## Impact

- `src/devops_cli/models/webhooks.py`
- `src/devops_cli/server/routes/webhooks.py`
- `src/devops_cli/server/service.py`
- `tests/test_server_service.py`
- `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`
- `k8s/README.md`

## Feasibility

- On origin/main `cf9f02c2`, `run_scoped_update` and `SCOPED_UPDATES` exist in `src/devops_cli/roadmap/run.py` (added in #2009).
- `GitHubWebhookPayload` already parses webhook bodies with Pydantic v2. Adding `WebhookIssue` with `number: int` parses the issue object without breaking other webhook payloads.
- `RepoWorker` runs a single-concurrency thread per `(repo, lane)`. Adding an internal scoped task queue ensures that scoped updates and full rounds run sequentially without racing.
- Tests verify offline execution through FastAPI `TestClient` and `InMemoryRoadmapStore`.

## Existing Tool Considered

The ADR 0009 router, Pydantic v2 validation models, and ADR 0017 scoped update engine already exist. No external library covers internal lane worker dispatch of webhook payloads. The change adds small glue logic in the existing modules and deletes no existing safety checks.
