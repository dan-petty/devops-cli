# Design

## Decisions

- **Use tenacity's sleep parameter for the Qdrant retry**: The project already uses tenacity, and docs/TESTING.md says waiting goes through the sleep and clock parameters the libraries take.
- **The process fake's delay advances the clock fixture's time**: This makes the fake consistent with the clock convention and removes real-time waits from tests that script slow commands.
- **A delay longer than the timeout raises the timeout error at once**: This matches the real behavior where a timeout fires before the delay completes, and removes the need for a real wait.
- **Test bodies use event waits or the clock fixture**: docs/TESTING.md requires that a test shows its behaviour without the clock: it waits for the event, or asserts on the waits of the clock fixture.

## Rejected alternatives

- **Keep time.sleep in the Qdrant retry and patch it in tests**: docs/TESTING.md says a direct time.sleep is a fallback for stdlib edges only, and the project already uses tenacity which has a sleep parameter.
- **Use freezegun for the clock**: docs/TESTING.md says freezegun is not used because it is unmaintained and its frozen monotonic clock hangs asyncio and tenacity.
- **Add a deadline to each test body**: docs/TESTING.md says no test bounds elapsed wall-clock time from above, and a loaded machine stretches the time.
