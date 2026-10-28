# Proposal

## Why

Issue #2523: a review of the change for #2474 found that the last rate limit of a request holds no other worker. The session sets the hold only for a refusal that it sends again, and `run_gh` returns from its backoff before the hold on its last attempt. The refusal that fails the round therefore holds nothing, and the other workers send requests at once, although GitHub asked for a wait with no request. GitHub's documentation says that requests sent while rate-limited "may result in the banning of your integration".

The review also found that no test fails when the hold in `run_gh`'s backoff is removed, or when `devops serve --service` stops giving its state directory to the Service. The rule comment above the alert `RoadmapServiceIdentityRefused` still says that a halt ends at a restart, and one output string has a contraction.

## What Changes

- The session's `retry_wait` holds the identity's requests for the wait of a rate limit also after the last attempt, and returns None for that attempt, so the request is not sent again. It records no throttle for the last attempt, because no retry waits.
- `run_gh`'s `_handle_attempt_backoff` holds the identity's requests for the backoff of a rate limit also on its last attempt, and sleeps no backoff there.
- `SessionGitHubAPI.handle_rate_limit_error` loses its early return for a spent retry count. `retry_wait` makes that decision.
- A test sends a secondary limit to each attempt of one worker's request, through the session and through gh, and finds that the next worker's request waits for the last refusal's wait. Each wait moves the clock, as in production. The test also fails when the hold in `run_gh`'s backoff is removed.
- A test starts the Service through `devops serve --service` over a state directory that holds a halt record and a budget record, and finds the Service halted with the requests of the window counted.
- The rule comment above `RoadmapServiceIdentityRefused` says that a halt stays after a restart until a person removes the halt record. `ServeMessages.state_unreadable` and the comments and docstrings that #2474 added say "cannot" in place of "can't".
- The change alters when the Service sends a request after a rate limit, so it carries a spec delta in `roadmap-service-limits`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-service-limits`: a rate limit holds every worker also when its request is not sent again.

## Impact

- `src/devops_cli/github/session_transport.py`, `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/server/service.py`.
- `tests/test_service_limits.py`, `tests/test_roadmap_run.py`.
- `k8s/monitoring/prometheus-values.yaml`.

## Feasibility

- gidgethub 6.0.0, `gidgethub/abc.py`, `_make_request`: the loop calls `handle_rate_limit_error` for every failed attempt, the last one too, with a 1-based `attempt`, and raises the error when the hook returns False. So the hook can hold the identity's requests on the last attempt and still let the request fail.
- `_run_gh_retry_loop` calls `_handle_attempt_backoff` for every failed attempt in `range(max_retries + 1)`, the last one too.
- On `origin/main` 6a5447a5, a test that routed three 403 answers with `retry-after: 60` to one session request, with each retry wait moving the clock, got `GitHubRateLimitError` after the waits `[60, 60]`. The next request of the identity was paced 0.24 s, not 60 s. `_handle_attempt_backoff` with a secondary-limit stderr extended the hold for attempts 0 and 1 of `max_retries=2`, but not for attempt 2.
- With the line `limiter.hold_requests(backoff)` removed from `_handle_attempt_backoff`, or the line `state_dir=state_dir,` removed from `serve.py`, `tests/test_github_rate_limiter.py`, `tests/test_service_limits.py`, `tests/test_roadmap_run.py`, `tests/test_server_service.py`, `tests/test_github_session.py` and the serve tests passed: 399 tests.
- `DEFAULT_GH_MAX_RATE_LIMIT_WAIT` is None, and no setting sets `max_rate_limit_wait`, so the Service never refuses a wait as too long. A hold on the last attempt therefore never raises in the Service.

## Existing Tool Considered

The change uses gidgethub's `handle_rate_limit_error` hook, which gidgethub calls for every failed attempt, and the existing `GitHubRateLimiter.hold_requests`. Nothing new is built. The change deletes the early return in `SessionGitHubAPI.handle_rate_limit_error` and the `attempt >= max_retries` condition at the start of `_handle_attempt_backoff`.
