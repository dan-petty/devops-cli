# Design

## Decisions
- Import the `clock` module and call `clock.monotonic()` and `clock.sleep()` at each poll, as other polling loops do. The fake clock then moves both readings, so the loop ends after 23 waits of 2 s.
- Keep the 45 s default timeout. Only the time source changes.

## Rejected alternatives
- Patch `time.sleep` and `time.monotonic` in the test: hides the production call; the seam exists for this.
- Assert an upper bound on wall time: the testing rules forbid it, and a loaded runner breaks it.
- Lower the timeout: changes production behavior.
