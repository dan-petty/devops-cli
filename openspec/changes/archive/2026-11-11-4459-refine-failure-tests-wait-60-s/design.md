# Design

## Decisions

- Wrap the shared `clock` in an autouse fixture that moves it to `START`. Every test keeps the name `clock` and gets the shared fake.
- A failure is recorded after the retries, and the fake clock moves by each wait. So the expected failure time is `START` plus the shifts of the test plus the recorded waits. The helper `_waited` returns the sum of `clock.waits`.
- Guard with `assert clock.waits`, not with an upper bound on elapsed time: the rule pack of the project rejects an elapsed-time bound, and a loaded host makes it flaky.

## Rejected alternatives

- Keep the `time_machine` traveller and patch `time.sleep` in the module. It repeats the shared fake.
- Move the clock in each test. It repeats setup and is easy to omit.
