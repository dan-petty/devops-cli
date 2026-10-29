# Design

## Context

`devops serve` starts the roadmap Service. Its worker lanes each run the refine job through `_run_refine_adapter` in `src/devops_cli/roadmap/run.py`. On Python 3.14 the import lock raises `_DeadlockError` when two threads import `pydantic_ai` for the first time at the same time. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- The Service imports `pydantic_ai` in the main thread before it starts the worker threads that run the refine job.

**Non-Goals:**

- A lock that makes a second lane wait for the first to finish the import. Ordering the import in the main thread removes the race instead.

## Decisions

- **Import at module level in `run.py`.** `src/devops_cli/commands/serve.py` reads `devops_cli.roadmap.run` in the main thread, before it starts the worker threads. A module-level import of `devops_cli.roadmap.refine` there reads `pydantic_ai` in the main thread, so no two lanes import it for the first time at the same time.
  - Rejected: keep the import inside `_run_refine_adapter`. Two lanes then import `pydantic_ai` for the first time at the same time, and the Python 3.14 import lock raises `_DeadlockError`.
  - Rejected: a lock around the import in each lane. A lock serializes the import, but it does not remove the first-import race across the two threads. Importing in the main thread removes the race.

## Risks / Trade-offs

- [The Service reads `pydantic_ai` in the main thread] → one module import, once, before the worker threads start. It costs one import at start.
