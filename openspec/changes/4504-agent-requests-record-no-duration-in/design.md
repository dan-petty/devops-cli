# Design

## Decisions
- **Before and after hook pair.** The repository already uses both hooks (`implement_limits.py`), and the after hook has the reply for the spend fields.
- **A `ContextVar` holds the start time.** It keeps one value for each request context, and concurrent runs do not overwrite each other. The after hook resets it.
- **Async hooks.** A sync hook runs in an executor, which copies the context, so a value set by the before hook would be lost. The after hook writes the record with `asyncio.to_thread`, so the SQLite write stays off the event loop. The duration is read before the write, so it excludes the write.
- **Monotonic clock.** `time.monotonic` does not move when the wall clock changes.
- **A retry is a request.** Each model request gets its own record and its own duration.

## Rejected alternatives
- **`model_request` wrap hook.** It also times the request, but it makes the spend hook one async wrapper with no example in the repository.
- **A timer around `Agent.run`.** It measures the whole run, not one request.
- **A module-level float.** Concurrent requests overwrite it.
