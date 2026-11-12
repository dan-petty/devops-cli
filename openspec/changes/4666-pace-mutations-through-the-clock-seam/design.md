# Design

## Decisions

- Both waits of the rate limiter go through the seam: the pause before a request and the backoff after a rate limit. With one wait on the seam and one on `time.sleep`, the `github_api` fake must replace two names of the limiter to record both.
- `gh_edge` requests `clock`. Each command test that scripts gh through `gh_edge` reaches the rate limiter, and the limiter waits between two gh writes. The fixture that prepares the limiter for a command test also answers its waits.
- `PacedClock` replaces the limiter's `clock` name. It keeps the contract of the `github_api` fake: the pauses go to `paced`, and no other sleep changes.

## Rejected alternatives

- Set the write interval of the limiter to 0 in the tests. The tests then do not see the interval, and the pacing test cannot prove the wait length.
- Replace the seam for each test in the root conftest. That is the work of the plan item that refuses real sleeps, which depends on this change. A frozen clock for each test also changes tests that need the wall clock to move.
- Add `clock` to the two `pr edit` tests of `tests/commands/test_pr_update.py`. The deletion of `devops pr update` changes that file now.
