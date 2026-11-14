# Design

## Context

`shutdown_tracer` persists in process state and test state leaks across tests of one xdist worker. The ADR cap test already filters by logger name.

## Goals

- Leave a usable tracer after the lifecycle test.
- Prove the cap test ignores another logger.

## Decisions

- **Reset at the end of the lifecycle test.** The test keeps its assertions on the shut tracer and then resets, so the rest of the worker starts clean.
- **A warning from the exporter logger.** The cap test emits the exact warning that a shut processor logs, and its logger filter keeps the assertion unchanged.

## Risks

- `reset_tracer` flushes and shuts the already shut tracer once more. It runs inside the lifecycle test, where no other test reads the logs.

## Tests

- The two files pass in one worker, telemetry first.
- The cap test's assertion holds with the extra warning.
