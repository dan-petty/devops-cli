# Design

## Decisions

- **Exempt a poll of `wait_until` with an explicit context manager that only `wait_until` enters.**: It is narrow, it has one call site, the guard keeps charging every other real sleep, and no test file changes.
- **Keep the charged total, the budget and a thread-local poll depth in `tests/support/sleep_budget.py`.**: The audit hook runs for every `time.sleep` of every thread, so the exemption must be thread-local, and a support module reaches both the hook and the waits with no list to edit.
- **Observe the plain-sleep failure with a `pytester` nested run that loads the real guard.**: The guard fails at teardown, so a test cannot catch the failure around its own sleep call; the nested run observes the real teardown error.
- **Make one poll pass the budget by monkeypatching `tests.support.waits.POLL_INTERVAL_SECONDS` to 0.3.**: `wait_until` reads the module constant at each poll, so one real poll sleep of 0.3 s passes the 0.25 s budget and the test costs 0.3 s.
- **Keep the budget name `REAL_SLEEP_BUDGET_SECONDS` and its value 0.25, in `tests/support/sleep_budget.py`.**: The issue asks that the budget stay as it is, and the name and value are the ones that the staged tree defines.
- **Exempt the polls of `wait_until` only, and not those of `wait_while_running`.**: The issue names `wait_until`, and the tests that use `wait_while_running` already carry `@pytest.mark.real_sleep`, as `tests/github/test_github_session.py:394:@pytest.mark.real_sleep` shows.

## Rejected alternatives

- **Detect the caller frame of the sleep in the audit hook.**: A stack walk on every sleep is slow and fragile, and it exempts any sleep that a test makes through that module.
- **Mark each test file that calls `wait_until` with `@pytest.mark.real_sleep`.**: It hides every real sleep in those tests, so the guard loses its value there, and it edits many files.
- **Subtract the polling time from the total after `wait_until` returns.**: It needs a second global counter that can drift, and it hides an over-budget sleep until after it happens.
- **Catch the failure with `pytest.raises(pytest.fail.Exception)` around `time.sleep(0.3)`.**: The guard reports the failure at teardown, not at the call, so the context manager does not catch it.
- **Call the charge function directly to show that a plain sleep still fails.**: It does not show that a plain `time.sleep` still fails the guard.
- **Poll for 0.26 s at the real 0.01 s interval.**: It costs 26 polls, and its timing depends on the load of the runner.
- **Fake the poll sleep at a seam.**: The guard then sees no sleep, so the test cannot show that the guard exempts it.
- **Adopt freezegun or time-machine for the guard.**: Both fake the clock and give no per-test real-sleep budget or exemption for a poll, and the alternatives check records no covering tool.
