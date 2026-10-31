# Tasks

## 1. Scoped webhook event dispatch in the Service

- [x] Add failing tests for Service-level webhook event dispatch:
  - Subscribed issues events (`opened`, `edited`, `reopened`) run the scoped update on the model lane and queue no full round.
  - Events that cannot be scoped (other actions, other events, or missing issue numbers) keep the whole-round hint to all lanes.
  - Lost delivery is processed by the subsequent reconciling poll.
  - Verification: `uv run pytest tests/test_server_service.py`
- [x] Add `WebhookIssue` to `src/devops_cli/models/webhooks.py` and `issue` field to `GitHubWebhookPayload`.
- [x] Update `RepoWorker` and `ServiceManager` in `src/devops_cli/server/service.py` with `enqueue_scoped` support.
- [x] Update `_hand_to_consumers` and `roadmap_consumer` in `src/devops_cli/server/routes/webhooks.py` to route to scoped updates.
- [x] Update documentation in `k8s/README.md` and `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`.
- [x] Verify all tests pass: `uv run devops ci`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1533-service-event-scoped-updates`
