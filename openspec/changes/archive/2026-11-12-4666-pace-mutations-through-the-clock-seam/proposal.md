# Proposal: #4666

## Why

The rate limiter called the stdlib `time.sleep` for its pause before a request and for its backoff after a rate limit (#4666). The clock seam `devops_cli.core.clock` and its `ClockFake` could not answer these waits, so each command test that sent two gh writes waited the one-second write interval for real. A PEP 578 audit hook recorded 72.31 s of real sleep in 170 calls in `tests/commands/test_pr_*.py` and `tests/commands/test_gh_cmd.py`.

## What Changes

- `acquire` and `_handle_attempt_backoff` of `src/devops_cli/github/rate_limiter.py` wait through `devops_cli.core.clock.sleep`. The real seam calls `time.sleep`, so each wait in production has the same length as before.
- The `gh_edge` fixture of `tests/support/gh_process.py` requests the `clock` fixture, so the waits of the rate limiter in a command test take no real time.
- `PacedClock` of `tests/support/fakes/github.py` replaces the limiter's `clock` name, not its `time` name, so the `github_api` fake records the pauses in `paced` as before.
- Two tests of `tests/github/test_github_rate_limiter.py` that recorded the waits on the stdlib `time.sleep` read `clock.waits`. The test of two threads holds both pauses with `clock.concurrent_sleeps(2)`, so neither thread moves the clock under the other.
- No consumer sees a change, so the change has no spec delta (`skip_specs: true`).

## Capabilities

None. The rate limiter waits for the same time, and only the tests answer the wait in a different place.

## Impact

- The pr and gh command tests take less CI worker time. The before and after measurements are in a comment of the pull request.
- The two `pr edit` tests of `tests/commands/test_pr_update.py` use `process_fake` with no `gh_edge`, so they still wait 6 s for real. That file belongs to the deletion of `devops pr update`, which runs now in another change.
- The change fits one pull request.

## Feasibility

- `src/devops_cli/github/rate_limiter.py` at origin/main `acb4e197b` called `time.sleep(sleep_duration)` in `acquire` and `time.sleep(backoff)` in `_handle_attempt_backoff`. No other call in the file waits.
- `devops_cli.core.clock.sleep` calls `time.sleep` when the test replaces nothing, and the `clock` fixture of `tests/support/fakes/clock.py` replaces it with `ClockFake.sleep`.
- A stack probe on the stdlib `time.sleep` audit event (Python 3.14.10) found one stack for every real sleep in the six files: `rate_limiter.py:1103`. The probe gave 72.31 s in 170 calls before the change and 0 s in the five files that use `gh_edge` after it.

## Existing Tool Considered

The clock seam `devops_cli.core.clock` and `ClockFake` over time-machine 3.5.1, which the project already uses. No new tool and no new code of our own. Cost: about 60,000 tokens and 2 hours. The change deletes the patch of the limiter's `time` module in `serve_github_api` and in `tests/github/test_service_limits.py`.
