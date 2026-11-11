# Proposal: #4459

## Why

Three tests of `tests/roadmap/refine/test_roadmap_refine_failure_class.py` wait on the real retry backoff of the model client: 30.3 s, 15.2 s and 15.2 s in CI. The module defines its own fixture `clock`, a bare `time_machine.travel(START, tick=False)`. It shadows the shared `clock` fixture of `tests/support/fakes/clock.py`, which the fixture `scripted_gateway` requests so that retries wait no time. So `time.sleep` and the clock seam are not replaced. AGENTS.md rule 5 makes a slow check a bug. Closes #4459.

## What Changes

- The module fixture `clock` is replaced by an autouse fixture that requests the shared `clock` (`ClockFake`) and calls `move_to(START)`.
- The tests take `ClockFake` as the type of `clock`. `ClockFake.shift` takes the `timedelta` values that they pass now.
- The recorded failure time now includes the retry waits that the fake clock answered, so the tests compute it with the new helper `_waited`.
- The timeout test asserts that `clock.waits` is not empty, so a shadow of the shared fixture fails.
- No production code, setting or timeout changes.

## Capabilities

- `refine-failure-test-clock` (new): the failure-class tests use the shared fake clock and guard it.

## Impact

- The three tests take well under 1 s each, about 60 s less of CI worker time per run.
- Another pull request (#4466) changes other tests; this change touches only this test module.

## Feasibility

- Command output: `uv run pytest tests/roadmap/refine/test_roadmap_refine_failure_class.py -n0 --durations=5` on `origin/main` took 31.7 s, 21.0 s and 15.7 s for the three tests.
- Source: line 57 of the module defines `clock`; `tests/support/roadmap_refine.py` `scripted_gateway` requests `clock: ClockFake`, so the module fixture shadows it.
- Source: `ClockFake` replaces `clock_seam.sleep`, `clock_seam.monotonic` and `time.sleep`, and records each wait in `waits`.
- No open pull request changes this module or the two support files.

## Existing Tool Considered

`time-machine`, through the project's `ClockFake` fixture. No new code. Cost: about 25,000 tokens and 30 minutes.
