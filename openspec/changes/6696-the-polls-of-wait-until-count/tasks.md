# Tasks

## 1. Charge real sleeps through a support module with a poll exemption

Kind: other. Reads: `tests/conftest.py`, `tests/support/waits.py`, `src/devops_cli/core/clock.py`. Changes: `tests/support/sleep_budget.py` (new), `tests/support/waits.py`, `tests/conftest.py`.

- [ ] 1.1 Add `tests/support/sleep_budget.py` with `REAL_SLEEP_BUDGET_SECONDS`, the charged total, a thread-local poll depth, `charge()`, `charged_seconds()` and `poll_sleep()`. Make the audit hook and the fixture of `tests/conftest.py` charge and read through that module, and enter `poll_sleep()` around the `clock.sleep(POLL_INTERVAL_SECONDS)` call of `wait_until` in `tests/support/waits.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py` passes

## 2. Test the poll exemption and the plain-sleep failure

Kind: other. Reads: `tests/invariants/test_hermetic_floor.py`, `tests/support/sleep_budget.py`, `tests/support/waits.py`. Changes: `tests/invariants/test_hermetic_floor.py`.

- [ ] 2.1 Add `test_a_wait_until_poll_past_the_budget_is_charged_nothing` to `tests/invariants/test_hermetic_floor.py`: monkeypatch `tests.support.waits.POLL_INTERVAL_SECONDS` to `0.3`, call `wait_until` with a condition that is false once and then true, and assert that `charged_seconds()` did not move. Extend `test_the_floor_refuses_real_sleeps_exceeding_budget` with an inner test that patches the poll interval to `0.3` and passes, and keep its plain `time.sleep(0.3)` case that fails
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py` passes

## 3. State the poll exemption in the test guide

Kind: other. Reads: `docs/TESTING.md`, `tests/support/waits.py`. Changes: `docs/TESTING.md`.

- [ ] 3.1 Add one bullet to the section Waiting for another thread of `docs/TESTING.md`: a poll of `wait_until` is charged nothing by the real-sleep budget, and every real sleep outside a poll is charged
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test shows that a `wait_until` whose condition holds after more than 0.25 s of polling does not fail the real-sleep guard.
- Group 2: A test shows that a plain `time.sleep` of more than 0.25 s in a test still fails the guard.
