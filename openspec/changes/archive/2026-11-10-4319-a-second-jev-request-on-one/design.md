# Design

## Decisions
- **One loop for the process.** `_jev_portal()` starts an anyio blocking portal on first use, under a lock, and stops it at exit. `reset_jev_portal` stops it too, and the test floor calls it after each test, as the floor resets every piece of process-wide state. A model keeps one client, and the client meets the same open loop on each request.
- **A public name for the call.** `decide_with_jev` replaces `_run_decide`. The model settings merge stays: the settings of the call win over the settings of the model.
- **Errors reach the caller.** `portal.call` raises in the calling thread the exception that `decide` raised, with the same type. A failed request does not stop the loop, so the next request runs.
- **The model stays the caller's choice.** A caller may pass a model (a test, or a model with its own thresholds). With no model, the function builds one from `settings`.

## Rejected alternatives
- **A new model for each call.** It does not fix a model that a caller passes in, and it opens a new client and a new TLS connection for each request.
- **A hand-written loop thread with `asyncio.run_coroutine_threadsafe`.** It repeats the portal of anyio, and the project would keep and fix it.
- **Close and rebuild the client after each call.** It needs private fields of pydantic_ai.
- **`async with model` in each request.** pydantic_ai replaces only a client that it made itself. The client here comes from the HTTP entry point, so the call would not help.
