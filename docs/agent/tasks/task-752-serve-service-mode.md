# Task: Service mode for devops serve with github webhook verification and per-repo queue (#752)

**Issue**: [#752](https://github.com/dan-petty/devops-cli/issues/752)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/feature, scope/cli, priority/p1-high

## Description
Adds a dedicated production service mode to `devops serve` (`devops serve --service`) for continuous in-cluster operation. The service receives, authenticates, and coalesces GitHub webhooks via `POST /webhooks/github`, runs an internal polling tick to schedule periodic repository syncs, and dispatches background tasks to a single-concurrency queue per managed repository.

Exposes `/healthz` (liveness monitoring background task health), `/readyz` (readiness and drain state), `/metrics` (Prometheus metrics registered on `GLOBAL_METRICS`), and formats all logs as single-line JSON without external dependencies. Dead webhook code (`WebhookEventDispatcher`, `WebhookEvent`, `GitHubWebhookVerificationError`) is completely removed.

## Acceptance Criteria
- [x] In-process delivery test in `tests/test_server_service.py` proves a delivery signed with a repo's secret receives 202 while the job is blocked on an unset event, executing on a separate daemon thread with a coalesced `TriggerBatch` (`counts == {("webhook", "issues", "opened"): 1}`). A second delivery receives 202 and coalesces into the pending batch.
- [x] Delivery authentication rejects missing signatures, wrong signatures, signatures from other managed repos, unmanaged repos, and managed repos with no secret with 401. Managed repos lacking secrets log a startup warning.
- [x] Duplicate deliveries identified by `X-GitHub-Delivery` within the 10,000 in-memory LRU window receive 202 on initial delivery and 200 on duplicate replay, queueing exactly one trigger.
- [x] `ping` events and deliveries where `sender.login` matches `service.machine_account` (case-insensitive) receive 200 and queue nothing.
- [x] Payload size limits enforce 25 MiB: requests exceeding the limit via `Content-Length` or streaming chunked transfer receive 413.
- [x] Unsupported `Content-Type` headers receive 415. Missing `X-GitHub-Event` or bodies that are not JSON objects receive 400.
- [x] Ten concurrent triggers for a repo while a job is running merge into exactly one subsequent run whose `TriggerBatch` counts all ten. Different repositories execute concurrently without cross-blocking. Per-repo concurrency never exceeds 1.
- [x] Polling tick loop advances time through injected clock/sleep fixtures, scheduling one `poll` trigger per repo at startup and after each `poll_interval_seconds` interval. `ServiceConfig` enforces `poll_interval_seconds >= 60` and `drain_timeout_seconds > 0`.
- [x] Job function exceptions increment `jobs_total{result="error"}` and log details while allowing subsequent triggers to run.
- [x] `/readyz` returns 503 prior to startup completion and during shutdown drain, and 200 while ready. `/healthz` returns 503 if any queue worker or the tick task fails or is cancelled.
- [x] Graceful shutdown waits up to `drain_timeout_seconds` for active jobs to complete while rejecting new webhook requests with 503. Job threads use `daemon=True` to allow clean termination.
- [x] The service app serves exactly four routes: `POST /webhooks/github`, `GET /readyz`, `GET /healthz`, and `GET /metrics`. Unmounted routes (`/`, `/docs`, `/api/v1/config`) return 404.
- [x] Prometheus metrics on `GET /metrics` record `webhook_deliveries_total`, `triggers_total`, `jobs_total`, `job_seconds_total`, `job_start_timestamp_seconds`, and `queue_depth`.
- [x] JSON log formatter formats all logs as single-line JSON containing `time`, `level`, `logger`, `message`, and contextual fields, with zero credential/secret/signature leakage.
- [x] CLI flags: `devops serve --service` rejects `--workers > 1` and `--reload` with exit code 2. Requires non-empty `service.repos`, present `service.machine_account`, and valid JSON object for `service.webhook_secrets` (failing with exit code 1 naming the credential).
- [x] Cleaned up dead webhook symbols: `git grep -n -E "WebhookEventDispatcher|WebhookEvent\b|GitHubWebhookVerificationError" -- src tests docs/ERRORS.md` returns 0 lines. Canonical `verify_webhook_signature` resides in `src/devops_cli/server/routes/webhooks.py` and reads `CONST_GH_WEBHOOK_SIGNATURE_HEADER`.
- [x] Fast in-gate tests in `tests/test_server_service.py` total under 1 s and open no network sockets. `uv run devops ci` passes.
- [x] `changelog.d/752.md` created; `CHANGELOG.md` and `docs/ROADMAP.md` remain untouched.
- Pending a person: local smoke test running `devops serve --service --port 8787`, verifying delivery flow, ready probe, and metrics emission.

## Deliverables
- [x] `src/devops_cli/config/settings.py`: Added `ServiceConfig` (`repos`, `machine_account`, `poll_interval_seconds`, `drain_timeout_seconds`) to `Settings`.
- [x] `src/devops_cli/config/options.py` & `src/devops_cli/config/env.py`: Added `service.webhook_secrets` and `ENV_SERVICE_WEBHOOK_SECRETS`.
- [x] `src/devops_cli/server/json_logs.py`: Added JSON log formatter.
- [x] `src/devops_cli/server/service.py`: Added `TriggerBatch`, per-repo queue workers, polling tick, probes, service metrics, and `create_service_app`.
- [x] `src/devops_cli/server/routes/webhooks.py`: Added `POST /webhooks/github` route with size checks, HMAC verification, replay deduplication, and machine-account filtering.
- [x] `src/devops_cli/commands/serve.py`: Added `--service` option, worker/reload guards, config validation, and JSON logging setup.
- [x] Cleaned up dead webhook files: deleted `src/devops_cli/github/graphql.py`, `tests/test_github_graphql.py`, removed `GitHubWebhookVerificationError`, `WebhookEvent`, `WebhookEventDispatcher` from exceptions, github module, and `docs/ERRORS.md`.
- [x] `tests/test_server_service.py`: Added test suite for service mode.
- [x] `tests/test_server.py`: Added CLI flag validation tests for `--service`.
- [x] `changelog.d/752.md`: Added release changelog fragment.
