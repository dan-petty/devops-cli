# Proposal

## Why

Issue #2161: GitHub suspended the machine account of the roadmap Service after it sent 800 to 1,700 requests an hour for two days. The Service then sent about 1,100 requests in the next hour, because every call got `Sorry. Your account was suspended (HTTP 403)` and the next round ran as usual. A job that fails also ran again at each round.

## What Changes

- When a round fails because GitHub refused the identity (HTTP 401, or HTTP 403 with `account was suspended`), the Service stops every job of every repository and lane. It logs one error, counts `devops_cli_service_identity_refused_total`, and starts no round until a person restarts it. The round that met the refusal runs no later job.
- `gh` output that says `account was suspended` is classified as `GitHubUnauthenticatedError`, in the gh-output table that already holds the 401 phrases.
- The Service keeps its GitHub requests under `service.github_requests_per_hour` (default 500). It counts the requests at the end of each round. When the last hour spent the budget, no round starts until the window has room. The poll interval is the configured one, or the longer one that the measured cost of a round and the budget give.
- A roadmap job that failed 3 rounds in a row does not run again until its input changes. A webhook trigger or a new change to an item is new input. A poll is not.
- Conditional reads of listings with `ETag` and `If-None-Match` exist already (#983), so this change adds no code for them.
- The change adds the capability `roadmap-service-limits`. The Service's behavior is observable, so it carries a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-service-limits`: when the Service stops, holds or skips GitHub work.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/serve.py`, `src/devops_cli/config/{constants,defaults,settings}.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_service_limits.py`, `tests/test_github_errors.py`.
- `docs/CONFIGURATION.md`, which `devops docs generate --sync-readme` rewrites.

## Feasibility

- The Loki records in the issue show the failure: `gh: Sorry. Your account was suspended (HTTP 403)` on each call after the suspension, and `Roadmap jobs failed: intake` at each round before it. The code agrees: `_execute_due_rows` logs each failure and the next round runs, and `RoundPause` reacts only to a GraphQL budget refusal.
- Conditional requests: `src/devops_cli/github/session_transport.py` keeps each GET answer with its ETag and sends `If-None-Match` (#983). GitHub documents that a 304 does not count against the primary rate limit.
- The request counter is the one of `GitHubRateLimiter.get_global_request_count`, which counts each paced request, 304 answers too, so the budget is conservative.
- Limit: the budget is read at the end of each round, so one round per worker can pass it.

## Existing Tool Considered

A rate limiter library such as `limits` or `pyrate-limiter` paces calls inside one process. The need here is different: a hard stop on a refused identity and a rule across rounds. The project already has `GitHubRateLimiter`, which counts the requests, so the change reads that count and builds only the hold. Cost to build: about 40,000 tokens and one hour. The change deletes no code.
