# Proposal

## Why

A test that waits for a thread handoff with `wait_until` fails the real-sleep guard of `tests/conftest.py` when the handoff takes more than 0.25 s, because each poll sleep counts toward the test's budget (#6696).

## What Changes

- Add `tests/support/sleep_budget.py` with the charged total, the budget, a thread-local poll depth, `charge()`, `charged_seconds()` and the `poll_sleep()` context manager.
- Make the audit hook and the fixture of `tests/conftest.py` charge and read through `tests/support/sleep_budget.py`, so a sleep inside a poll of the current thread is charged nothing.
- Enter `poll_sleep()` in `wait_until` around each `clock.sleep(POLL_INTERVAL_SECONDS)` poll of `tests/support/waits.py`.
- Add a floor test that a 0.3 s poll of `wait_until` is charged nothing, and extend the pytester guard test with an inner `wait_until` case that passes.
- State the exemption in `docs/TESTING.md` beside the rule for waits.
- This change has no spec delta, because it changes only test support and a document, which no consumer of `devops` observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/TESTING.md`
- Tests: `tests/support/sleep_budget.py`, `tests/support/waits.py`, `tests/conftest.py`, `tests/invariants/test_hermetic_floor.py`

## Feasibility

- The path `tests/conftest.py` is a file of the staging commit.
- The path `tests/support/waits.py` is a file of the staging commit.
- The path `tests/github/test_github_session.py` is a file of the staging commit.
- `read_file` of `tests/conftest.py` lines 757-809 showed `tests/conftest.py:def _install_real_sleep_hook` adding each `time.sleep` event to `_REAL_SLEEP_TOTAL`, and `tests/conftest.py:def refuse_real_sleeps` failing a test above `tests/conftest.py:762:REAL_SLEEP_BUDGET_SECONDS: float = 0.25`.
- `read_file` of `tests/support/waits.py` showed `tests/support/waits.py:37:POLL_INTERVAL_SECONDS: Final[float] = 0.01` and `tests/support/waits.py:49:clock.sleep(POLL_INTERVAL_SECONDS)`, the real poll that the guard charges.
- `read_file` of `src/devops_cli/core/clock.py` showed `src/devops_cli/core/clock.py:10:time.sleep(seconds)`, so a poll of `wait_until` reaches the audit hook of `time.sleep`.
- `read_file` of `tests/github/test_github_session.py` lines 421-453 showed `tests/github/test_github_session.py:446:sent = wait_until(lambda: bool(github_api.sent))` in a test with no `real_sleep` marker, so its only real sleep is the poll.
- `search_code` for `wait_until` showed the same poll in `tests/github/test_service_limits.py:1060:assert wait_until(lambda: len(seen) == 3)`, the test that comment 3 of the issue reports.
- `read_file` of `tests/invariants/test_hermetic_floor.py` showed `tests/invariants/test_hermetic_floor.py:def test_the_floor_refuses_real_sleeps_exceeding_budget`, a pytester run through `_run_with_floor` that keeps the plain-sleep case.
- `references` for `REAL_SLEEP_BUDGET_SECONDS` listed `tests/conftest.py` as the only file that holds the constant, so the move of the constant touches no other file.
- No function that this plan calls needs a checkout, a client or a network: `wait_until` reads a condition and calls `clock.sleep` in the test process.
- The verify commands `uv run devops ci test tests/invariants/test_hermetic_floor.py` and `uv run devops ci docs` use `uv`, `devops` and `pytest` from the runner image, name no program of `NOT_IN_RUNNER`, and the pod runs as non-root with a read-only root, so the tests write only under pytest's temporary directory.
- A failed `uv run devops ci test` fails as class `test`, which a repair round fixes, and a failed `uv run devops ci docs` fails as class `lint`, which a repair round fixes.
- The first check that the implementation runs against the real system is `uv run devops ci test tests/invariants/test_hermetic_floor.py`, followed by `uv run devops ci docs`.
- The budget stays `REAL_SLEEP_BUDGET_SECONDS` = 0.25 s and the poll interval stays 0.01 s; a poll of `wait_until` is charged nothing and every real sleep outside a poll is charged.

## Existing Tool Considered

freezegun and time-machine fake the clock and give no per-test real-sleep budget or exemption for a poll helper, so the guard stays the repository's own code, at a written cost of about 8000 tokens to build, keep and fix, and about 2 hours elapsed.

## Dependencies

None.
