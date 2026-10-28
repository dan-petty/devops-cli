# Design

## Context

Every GitHub request of the Service goes through the identity's `GitHubRateLimiter`, from the session and from `run_gh`. `hold_requests(wait)` sets a time before which `acquire` schedules no request of the identity, for every resource and thread (#2474). The session calls it from `retry_wait`, and `run_gh` from `_handle_attempt_backoff`. Before this change, both returned before the hold when the request had no retry left.

## Decisions

- **Hold before the retry decision.** In each path, the hold comes first and the check for a retry left comes after it. One call in each path covers each rate limit, the last one too, so one test catches the removal of either call.
- **The wait of the last attempt is the wait of a retry.** The session reads it from `retry_delay` with the attempt's number: the `retry-after` of the answer, else the time to the reset of a spent quota, else the jittered backoff. `run_gh` reads it from `calculate_backoff_delay`. This is the wait that the next retry would take, and GitHub's documentation asks for it before the next request.
- **No throttle for the last attempt.** `record_throttle` observes the wait before a retry in `devops_cli_github_throttle_wait_seconds`. The last attempt has no retry, and the earlier attempts of the request already recorded their throttles, so the alert `RoadmapServiceGitHubThrottled` fires as before.
- **The test moves the clock at each wait.** With a clock that stands still, the hold of the first refusal still covers the next request, and the test cannot tell the last refusal's hold from the first one's. The test routes the rate limiter's `time.sleep` and the session's `sleep` through `ClockFake`, so each retry wait takes its time.
- **The serve test reads records, not arguments.** It writes a halt record and a budget record into `service_state_dir()`, starts the Service through `devops serve --service`, and reads `pause.halted()` and `budget.spent()`. A test of the arguments of `create_service_app` would pass for a directory that the Service does not read.

## Rejected Alternatives

- **Connect a `pause_until` reader in `serve.py` for the failed round.** The round of the last refusal fails, so a reader could read a time from its error. But `run_gh`'s failure becomes a `GitHubRateLimitError` from gh's stderr, which has no wait time (`GitHubRoadmapStore._failure`), and the workers that are in a round would not stop. The limiter is the one place that every request goes through, and it already knows the wait.
- **Hold for a wait past `max_rate_limit_wait`.** `retry_delay` refuses such a wait, and the request fails with no hold. `DEFAULT_GH_MAX_RATE_LIMIT_WAIT` is None and no setting sets it, so the Service never meets this case.
- **Add a check for contractions in every output string.** Other strings in `src/devops_cli/lang/en/messages.py` that #2474 did not add also have "can't". The finding names the string that #2474 added, and the change fixes the text that #2474 added.

## Risks

- A request that fails on its last rate limit now holds every request of the identity for one more wait, up to `DEFAULT_GH_SECONDARY_MAX_CAP` (300 s) for a secondary limit with no `retry-after`. GitHub asks for this wait, so the Service sends fewer requests that GitHub refuses.
