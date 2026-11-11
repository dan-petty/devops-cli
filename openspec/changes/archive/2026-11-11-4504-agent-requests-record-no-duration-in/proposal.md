# Proposal: #4504

## Why
Since #4237, the stage, refine and alternatives runs write their spend records through the hook of `build_agent`. The hook passes no `duration_seconds`, so every record holds 0.0, and the mean duration of a spend report is too low. Before #4237, `record_run_spend` wrote the time of the run. Closes #4504.

## What Changes
- The spend hook of `build_agent` times each model request with a monotonic clock and gives the seconds to `track_request_spend`.
- The hook now has two parts: a before hook that keeps the start time, and an after hook that writes the record. The hooks live in `_spend_capability` so `build_agent` stays simple.
- The after hook writes the record in a worker thread (`asyncio.to_thread`), as the plain function hook did before.

## Capabilities
- Modified: `ai-spend-pricing`.

## Impact
- `src/devops_cli/ai/client/factory.py`, `tests/ai/client/test_agent_factory.py`.
- Every record of the hook holds the seconds of its request. The backend breakdown averages the records that name `served_by`; the hook passes no `served_by` today, so it does not list those rows (a follow-up issue covers it).

## Feasibility
- `track_request_spend` takes `duration_seconds` (default 0.0) and `record_request` stores it rounded to 4 places. The hook did not pass it, so the premise holds.
- pydantic-ai runs a plain `def` hook in an executor, where a `ContextVar` set by the before hook does not reach the after hook. So both hooks are `async def`, and the record is written with `asyncio.to_thread`, which copies the context.
- A request that raises runs no after hook (`on_model_request_error` is the error path), so a failed request writes no record. A test shows the stale start time does not reach the next request.

## Existing Tool Considered
- pydantic-ai `Hooks` (`before_model_request`, `after_model_request`) gives the two points. It has no per-request duration field, so the hook computes the seconds. No new library is needed.
