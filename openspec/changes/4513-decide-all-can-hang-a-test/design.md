# Design

## Decisions

- One event loop for all requests of one `decide_all` call, in the calling thread. A model that the requests share then uses its lock and its client on the loop that bound them. A model that `decide_all` builds for a request still closes its client on that loop (#4319).
- `asyncio.timeout(timeout)` wraps each request inside its semaphore slot. The wait for a free slot does not use the time of the request, and the limit also covers the enter and exit of the model, where the lock wait was.
- `asyncio.gather` with no `return_exceptions` raises the first error, as before. `asyncio.run` then cancels the other requests and lets each close its own client.
- The default `timeout` is `CONST_ROADMAP_JEV_TIMEOUT_SECONDS`, the constant of the project for one Jev request.
- The timeout test calls `decide_all` in a thread of the test and waits for its outcome with `THREAD_HANDOFF_BOUND_SECONDS` (docs/TESTING.md). The test releases the held request in `finally`, so on the base the test fails at the bound and the worker does not stay stuck.

## Rejected alternatives

- Keep the threads and add `future.result(timeout=...)`. The exit of the `with ThreadPoolExecutor` block joins the stuck thread (the traceback of #4513), and the exit of the interpreter joins pool threads too. A shared model also still crosses loops.
- Build a model for each thread. A caller can give its own model (the decision point and the tests do), and `decide_all` cannot copy it.
- `asyncio.TaskGroup` or an AnyIO task group. Both wrap the first error in an `ExceptionGroup`, which `FAILED` does not catch, so the step would not fail open. AnyIO would also add nothing that the standard library does not give.
- Rely on the `timeout` setting of the model. That is the HTTP timeout of the client, and it does not cover the lock wait or a transport that does not answer.
