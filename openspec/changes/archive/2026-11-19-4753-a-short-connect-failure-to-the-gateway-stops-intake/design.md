# Design

## Decisions
- Configure connect failure retries with up to 10 attempts and jittered exponential backoff.
- Bound total retry duration to the outer read timeout minus one connect timeout (5 seconds).
- Distinguish pre-output resets from mid-stream resets: retry only when no chunk has been emitted.
- Record stream spend with finish reason `error` when a stream fails mid-flight.
- Format `_connection_error` with the exception class, cause chain root name, and backend host.
- Keep the HTTP transport as the single retry layer to prevent multiplying retry attempts.

## Rejected alternatives
- Keep 5 retry attempts: Rejected because transient drops can exceed 38 seconds.
- Retry indefinitely during read timeout: Rejected because excessive waits degrade interactive commands.
- Custom retry loop in the client: Rejected because tenacity handles backoff and jitter cleanly.
