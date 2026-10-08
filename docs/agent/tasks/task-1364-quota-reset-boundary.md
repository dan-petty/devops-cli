# Task: A gh call at a quota window's reset waits out the reset second instead of failing (#1364)

**Issue**: [#1364](https://github.com/dan-petty/devops-cli/issues/1364)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p2-medium
**Scope**: type/bug, scope/github

## Description

Once the clock passed a stored quota's reset, `_resolve_quota_state` refreshed from `gh api rate_limit`. It then checked GitHub's answer against the clock it had read before the refresh. GitHub's `reset` is whole seconds, and GitHub keeps reporting a window for up to about 2 s after its reset. So an answer that still carried the ended window raised "Rate limit state for subcommand 'core' is in an unknown or broken state". The Service hit this about once an hour, because its 300 s poll lines up with GitHub's hourly window, and each hit cost a round, a job or a metrics read.

A passed reset now means the same thing everywhere in `src/devops_cli/github/rate_limiter.py`: the window has ended.

- `_refresh_from_github` returns the reset GitHub reported for each resource its answer gave both `remaining` and `reset`. `_extract_rate_limit_endpoint_response` and `_update_single_resource_quota` report that map.
- `_resolve_quota_state` returns the stored quota while it is valid, and otherwise refreshes once. It raises `GitHubRateLimitError` when the refresh fails (unchanged), when the answer has no usable entry for the resource, or when the clock is more than `CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS` (5 s) past the reset GitHub just reported. Otherwise it returns the refreshed quota, even when its reset has passed.
- `calculate_delay` no longer raises "time until reset must be non-negative". At a reset that has passed, `_passed_reset_delay` returns the time until `CONST_GH_RATE_LIMIT_RESET_MARGIN_SECONDS` (1 s) past it, and logs one INFO record. `acquire` sleeps that delay after it releases the lock, as before.
- The dead `_is_refreshing` flag is gone.

## Acceptance Criteria

- [x] **A passed reset means the window has ended.** At a stored reset at or before the clock, the call refreshes once. When GitHub's answer still has a reset at or before the clock, within the bound, the call waits until a second past that reset and runs; nothing raises. The wait is `acquire`'s sleep, outside `self._lock`. Tests: `test_a_call_just_past_a_reset_waits_out_the_reset_second` (one refresh, one recorded 0.5 s wait, the command once) and `test_a_clock_within_the_bound_past_the_reset_runs_and_refreshes_again` (no wait, a refresh before each call).
- [x] **A clock far from GitHub's still fails closed.** A fresh reset more than 5 s behind the clock raises `GitHubRateLimitError` saying the clocks disagree. The error names the resource, the reported reset and the local clock in UTC, and the gap. The command never runs. The gap is measured on GitHub's fresh answer only: a stored window that ended an hour ago refreshes into the new one and paces from it. Tests: `test_a_clock_past_the_bound_fails_closed_naming_both_clocks` and `test_a_call_after_an_idle_hour_paces_from_the_new_window` (one recorded 0.72 s wait).
- [x] **Both numbers are named constants** in `src/devops_cli/config/constants.py`: `CONST_GH_RATE_LIMIT_RESET_MARGIN_SECONDS` cites GitHub's whole-second `reset` and PyGithub 2.10.0's margin (`github/GithubRetry.py:173-174`), and `CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS` cites the measured 0.72–2.07 s gaps.
- [x] **A passed reset means the same thing everywhere in the module.** The "time until reset must be non-negative" raise and `test_calculate_delay_rejects_negative_time_left` are deleted. The boundary tests cover the behaviour through `run_gh`.
- [x] **A request sent after the reset is not counted against the old window.** `_acquire_locked` still records use only on a valid entry. The boundary test reads the stored `core` quota back unchanged (`remaining` 7, `used` 4993).
- [x] **Truly unknown state still fails closed.** A failed refresh raises with gh's failure (`test_a_failed_refresh_fails_closed_naming_the_gh_failure`). An answer without the resource raises naming it and the resources the answer does report, even over a stale stored entry (`test_an_answer_without_the_resource_fails_closed_over_a_stale_entry`). In both cases the command never runs.
- [x] **The boundary shows in the log.** Each call at a passed reset logs one INFO record: `[RateLimit] '<resource>' quota window reset at <UTC>, <s>s ago; waiting until at least <UTC>`, the reset plus the margin. A write may wait longer, for its own pacing.
- [x] **`_is_refreshing` is deleted.**
- [x] **Two worker threads** at the boundary each refresh, wait 0.5 s and run, and neither raises (`test_two_workers_at_the_reset_both_wait_it_out_and_run`).
- [x] Tests are in `tests/test_github_rate_limiter.py`. They fake gh at `subprocess.run` only, rely on the autouse `pin_github_session` for the token, freeze `time.time`, record `time.sleep`, seed the stored quota through `update_quota`, make no network call and patch no devops-cli name. They assert the whole list of recorded waits.
- [x] `changelog.d/1364.md` records the fix. `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
- [x] `uv run devops ci` passes.
- Pending a person: 7 days after the Service runs an image with this fix: `sum(count_over_time({namespace="devops", container="service"} |= "unknown or broken" [7d]))` returns no data.
- Pending a person: over the same 7 days, `{namespace="devops", container="service"} |= "quota window reset at"` shows at least one line, and every `<s>s ago` it reports is below 5 s.

## Decisions and deviations

- **Where the boundary is logged.** The INFO record is written in `calculate_delay`'s passed-reset branch (`_passed_reset_delay`), not in `_resolve_quota_state`. That is where the wait is computed, so the record states the wait the call actually takes. It also covers a reset that passes between `_resolve_quota_state`'s clock read and `calculate_delay`'s. `_resolve_quota_state` only returns a quota or raises.
- **The wait at a passed reset** is `max(min_interval, reset + 1 s - now, 0)`. A clock more than 1 s past the reset, but within the bound, runs at once, and the next call refreshes again. Waiting longer would not ensure GitHub's next window either, since GitHub reported an ended window up to 2.07 s after its reset.
- **What a refresh covered** is the map of resources whose answer had both `remaining` and `reset`. `_apply_quota_update` keeps a stored reset when an answer's `reset` is missing, so the gap is measured on the reset GitHub just reported, never on the stored entry.
- **Error details.** The clock error carries `reported_reset`, `local_clock` and `gap_seconds`, and the missing-resource error carries `reported_resources`. Neither carries `reset_epoch`. #1400 owns the rule for which errors pause the Service; its acceptance criteria already say this item's state errors pause nothing, and `GitHubRateLimitError` stringifies every detail value.
- **Docs.** AGENTS.md's `run_gh` summary (Zero Bare `gh` Invocations) now names the wait at a passed reset. The rate limiter's module, class, `run_gh`, `_resolve_quota_state`, `_refresh_from_github` and `calculate_delay` docstrings now say the same. AGENTS.md's "Honoring HTTP 429 & Secondary Limits" bullet stays as it is: it describes the backoff after a 429 or 403, which this change leaves alone. `docs/ERRORS.md` stays as it is, because `GitHubRateLimitError`'s class and docstring are unchanged.
- **Test infrastructure.** #1320 (clock fixture), #1321 (gh process fake), #1313 (test move) and #1016 (constant placement) have not landed, so the issue's fallbacks apply. Unlike the `tests/test_github_rate_limiter.py` precedent it follows, the tests do not set `process._github_token`.
- **`_utc_text`.** It formats a UTC second with `time.strftime`. It is shared by the clock error, the INFO record and the existing primary-wait error, which had the same format inline.

## Deliverables

- [x] `src/devops_cli/github/rate_limiter.py`: `_resolve_quota_state`, `_refresh_from_github`, `calculate_delay` with `_passed_reset_delay`, `_extract_rate_limit_endpoint_response` and `_update_single_resource_quota` reporting what the answer covered, `_unreported_resource_error`, `_check_clocks_agree`, `_utc_text`, and `_is_refreshing` removed.
- [x] `src/devops_cli/config/constants.py`: `CONST_GH_RATE_LIMIT_RESET_MARGIN_SECONDS`, `CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS`.
- [x] `tests/test_github_rate_limiter.py`: the seven boundary cases. `test_calculate_delay_rejects_negative_time_left` is deleted.
- [x] `AGENTS.md`: the `run_gh` summary.
- [x] Changelog fragment: `changelog.d/1364.md`.
