# Proposal

## Why

Issue #2474: a go-live review of the roadmap Service found three gaps in how the Service stops when GitHub refuses its requests. GitHub suspended the previous identity on 2026-10-11 (#1562), and requests sent after a refusal are the behavior most likely to make GitHub block the App.

- The halt, the hourly budget window and the failure ledger were in memory only (`RoundPause`, `RequestBudget` in `src/devops_cli/server/service.py`; `FailureLedger` in `src/devops_cli/roadmap/run.py`). A crash or a restart after a refusal started again at full speed.
- A rate limit stopped only the thread that got it. The session waited in that request's coroutine, and `run_gh` slept in its own thread, so the other 15 workers sent requests during the wait.
- The gh-output table did not read a suspended App installation as a refused identity, and the HTTP classifier did not read a 403 with no rate-limit header as one. A suspended installation whose current token was still valid did not halt the Service.

## What Changes

- The Service keeps three files in the `roadmap` directory of the data directory, beside the `schedule.json` of each repository, on volume `roadmap-service-home`: `service-halt.json`, `service-budget.json` and `service-failures.json`. `service_state_dir()` gives the directory. A restart reads the files back. A file that exists and cannot be read stops the start with an error that names it.
- A halt stays after a restart. The Service logs one error line at start and counts the refusal once in `devops_cli_service_identity_refused_total`, so the alert `RoadmapServiceIdentityRefused`, which fires while that counter is above 0, holds through the restart. A person removes `service-halt.json` and restarts the Service to clear the halt. The alert's description, its promtool test and its row in `k8s/README.md` say so.
- The budget keeps, for each round of the last hour, the time the round ended and the requests sent since the round before. The sum of these is the requests of the window, so the count in a new process can start at any value.
- The ledger keys each failure by a SHA-256 digest of the round's input, so the record holds a string.
- `serve --service` builds the lane jobs with `service_jobs(state_dir)`, which shares one ledger kept in the directory. `SERVICE_JOBS` and `SERVICE_FAILURES` are deleted.
- A rate-limit wait in the session or in `run_gh` holds every request of the identity, from all threads, until the wait ends (`GitHubRateLimiter.hold_requests`).
- The gh-output table reads "installation has been suspended" and "suspended your access" as a refused identity. The HTTP classifier reads a 403 to a write whose answer has no `x-ratelimit-*` header as a refused identity (`GitHubUnauthenticatedError`).
- `k8s/README.md` says where the files are and how to clear a halt.
- The change alters the Service's behavior after a restart, after a rate limit and after a refusal, so it carries a spec delta in `roadmap-service-limits`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-service-limits`: a refused identity includes a suspended installation and a header-less 403 to a write; a restart keeps the halt, the budget window and the ledger; a rate limit holds the requests of every worker.

## Impact

- `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/serve.py`, `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/github/session_transport.py`, `src/devops_cli/github/error_classifier.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_service_limits.py`, `tests/test_github_errors.py`, `tests/test_roadmap_run.py`, `tests/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`.
- `k8s/README.md`, `k8s/monitoring/prometheus-values.yaml`.

## Feasibility

- Each line that the issue names was read on `origin/main` 0c2cba63. `RequestBudget.__init__` starts its samples from the count at start, `RoundPause._halted` starts `False`, and `FailureLedger._failed` starts empty, with no file read or write. `commands/serve.py` passes no `pause_until` to `create_service_app` since commit 84f02a1a. `CONST_GITHUB_UNAUTHENTICATED_PATTERNS` holds "account was suspended" only, and `_HTTP_CLASSES` reads no rate-limit header for a 403.
- `SessionGitHubAPI.handle_rate_limit_error` waits with `anyio.sleep` on the portal's loop, and `_handle_attempt_backoff` calls `time.sleep` in the calling thread. `GitHubRateLimiter.acquire`, which every worker's request goes through, did not know of either wait. The new test showed the second worker's request paced 0.42 s after a 403 with `retry-after: 60` before the change.
- On `origin/main` 0137f231, #2496 added `RoadmapServiceIdentityRefused` with `max by (identity) (devops_cli_service_identity_refused_total{job="roadmap-service"}) > 0`, and its description said that the halt ends at a restart. A new process starts that counter at 0, so the change counts a kept halt once at start and corrects the description.
- `deployment.yaml` sets `DEVOPS_CLI_DATA_DIR=/home/devops/.data` and mounts PVC `roadmap-service-home` at `/home/devops`, and `run_due_jobs` writes `<data dir>/roadmap/<owner>/<name>/schedule.json`. So the `roadmap` directory is on the volume.
- GitHub's REST documentation, "Rate limits for the REST API": the `x-ratelimit-*` headers are "sent with each response"; for a secondary limit, "you should not retry your request until after that many seconds has elapsed" when `retry-after` is present, else "wait for at least one minute"; "Continuing to make requests while you are rate limited may result in the banning of your integration."
- GitHub's documentation for a suspended installation says only that the App "cannot access resources owned by that installation account" and names no status or message. Public reports give the 403 text: "This installation has been suspended" to `POST /app/installations/{id}/access_tokens` (Netlify forum, google-gemini/gemini-cli#12033), and `Sorry. This installation owned by <owner> suspended your access at <time>.` (probot/probot#1482).
- The recorded GitHub answers in `tests/fixtures/github_api/recorded_answers.json` (2026-10-19) show that GitHub's 401 "Bad credentials" has no `x-ratelimit-*` header, while its 404 and 422 to an accepted identity have all five.
- One part of the premise holds only in part. The roadmap store sends its writes through `gh api`, which prints no header without `-i`, and the Service sends no write through the session. So the header rule covers a write through the session, and the Service's own writes depend on the text of the gh-output table. The change adds no `-i` to the store's writes; the design records why.

## Existing Tool Considered

The change uses what the code already has: the atomic `write_json_file`, pydantic's `TypeAdapter` for the records, the rate limiter that paces every request of the identity, and GitHub's documented `retry-after` and `x-ratelimit-*` headers. A store such as SQLite or Valkey would add a dependency for three small files that one process writes. Nothing new is built. The change deletes `SERVICE_JOBS`, `SERVICE_FAILURES` and the in-memory sample list of `RequestBudget`.
