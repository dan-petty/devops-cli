# Proposal: #4513

## Why

`decide_all` can stop a test worker for good (#4513). It sent each request in its own pool thread, each with its own event loop from `asyncio.run`, and the callers give one model to all of the requests. The provider of that model holds one `anyio.Lock` and one HTTP client, and both bind to the loop that first uses them. A request that waits for the lock on a second loop does not wake up when the first loop releases it. The calling thread then waits on the pool with no time limit, and the pool exit joins the stuck thread again, so pytest-timeout cannot stop the test. Two CI shards stopped at their 30-minute job limit on 2026-11-11. Closes #4513.

## What Changes

- `decide_all` sends all requests of one call on one event loop in the calling thread, with `asyncio.gather`. An `asyncio.Semaphore` keeps the limit of `CONST_ROADMAP_DECISION_STEP_CONCURRENCY` requests at the same time.
- `asyncio.timeout` bounds each request, the wait for the lock of the model included. A request that does not end raises `TimeoutError`, which is in `FAILED`, so the step fails open.
- The default `timeout` of `decide_all` is `CONST_ROADMAP_JEV_TIMEOUT_SECONDS`, the limit of one Jev request, in place of the literal `30.0`.
- The fake of the Jev endpoint records the event loop of each request and can hold a request open until the test releases it.

The change alters behavior that a caller sees (a stuck request now ends in `TimeoutError`), so it carries a delta of the `decision-steps` capability.

## Capabilities

- `decision-steps`: ADDED requirement for one event loop and a time limit for each request.

## Impact

- `src/devops_cli/roadmap/decision_step.py`: `decide_all` and `_decide_one`; the `ThreadPoolExecutor` fan-out is removed.
- `tests/support/fakes/jev.py` and `tests/roadmap/test_roadmap_decision_step.py`.
- `src/devops_cli/config/constants.py`: the comment of `CONST_ROADMAP_JEV_TIMEOUT_SECONDS` names the decision step as a second user.
- A caller must not call `decide_all` from a thread that runs an event loop, because `asyncio.run` refuses that. The callers (the stage review screen, the screen evaluation and the decision-point resolver) are synchronous code, as are the other Jev calls of `devops_cli.ai.jev`, which also use `asyncio.run`.
- The change fits one pull request.

## Feasibility

- Library source, pydantic-ai-slim 2.59.0: `Provider._enter_lock` in `pydantic_ai/providers/__init__.py` is a cached `anyio.Lock`, and its comment says that the lock binds to the event loop on which it is first used. `Provider.__aenter__` and `__aexit__` take that lock for each request. anyio is 4.15.1.
- The traceback of #4513 shows the main thread in `ThreadPoolExecutor.__exit__` → `shutdown` → `Thread.join`, and the pool thread in `asyncio.run` → `selectors.select`, so the wait has no limit at two levels.
- Command output on base 5f75d256 with the new tests: `uv run pytest tests/roadmap/test_roadmap_decision_step.py` gave `test_a_shared_model_serves_every_request_on_one_event_loop - assert 3 == 1` (three loops for one model) and `test_a_request_that_is_never_answered_ends_in_timeout_error - _queue.Empty` after the 30 s bound of the test.

## Existing Tool Considered

The standard library `asyncio` covers the need: `asyncio.run`, `asyncio.gather`, `asyncio.Semaphore` and `asyncio.timeout`. No new dependency. The change deletes the `ThreadPoolExecutor` fan-out of `decide_all` and the `asyncio.run` for each request in `_decide_one`.
