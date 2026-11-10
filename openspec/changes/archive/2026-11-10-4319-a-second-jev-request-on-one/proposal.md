# Proposal: #4319

## Why
A second request on one Jev model fails with `RuntimeError: Event loop is closed`. `_run_decide` in `src/devops_cli/ai/jev.py` ran each request with `asyncio.run`. The HTTP client of a model keeps its pooled connections, and they belong to the event loop that opened them. `asyncio.run` closes that loop at the end of the request. The tests did not show the defect, because `httpx2.MockTransport` has no loop. Callers that keep a model (the eval of the completeness check) built a new model for each request as a workaround. Closes #4319 and closes #4309.

## What Changes
- Add the public function `decide_with_jev(request, *, model=None, settings=None, model_settings=None)` to `src/devops_cli/ai/jev.py`. It builds the Jev model from `settings` when the caller gives no model, merges the model settings with the settings of the call (the call wins), and returns the `DecisionResponse`.
- The function runs every request on one event loop that stays open for the life of the process. An anyio blocking portal (`anyio.from_thread.start_blocking_portal`) starts the loop in a thread on first use and stops it at exit.
- Remove the private `_run_decide`. All helpers of `jev.py` call `decide_with_jev`. `jev_ask.py` and `roadmap/jev_completeness.py` call it too, and drop their own `asyncio.run`.
- `run_cases` of the completeness eval takes one `model` and not a factory of models.

## Capabilities
- New capability `ai-jev-decide`: one public function, and one model that serves every request.

## Impact
- A caller needs no private name, no `asyncio.run` and no new model for each request.
- The private name `_run_decide` is gone. Branches that import it (feat/4282-jev-screen-before-verify, feat/4298-jev-decides-intake-labels) call `decide_with_jev(request, model=model)` instead. They keep `create_jev_model(settings=...)`.
- A caller on a thread that runs an event loop works now. `asyncio.run` raised in that case.
- No new dependency: `anyio` is already pinned.

## Feasibility
- Reproduced first. `tests/ai/test_jev_one_model_many_requests.py::test_a_helper_answers_twice_with_one_model` sends two requests on one model to a keep-alive server on loopback. On `origin/main` the second request raises `RuntimeError: Event loop is closed` from `selector_events.py` `_check_closed`. The test is the `fail-to-pass` run.
- Library source. `pydantic_ai.providers.Provider._refresh_http_client` replaces a client that moved to another loop, but only for a client that the provider made itself (`_own_http_client`). Here `create_pydantic_ai_provider` passes the client of the HTTP entry point to the provider, so the egress guard stays. The provider never replaces a client that was passed in, so the library cannot repair this case.
- `anyio.from_thread.start_blocking_portal` (anyio 4.15.1, installed) runs one loop in a thread, and `portal.call(func, *args)` runs a coroutine function on it and returns the result or raises its exception with the same type.

## Existing Tool Considered
The anyio blocking portal covers the need: it is maintained, MIT licensed and already a dependency. The change adds about 15 lines for its lifetime. Rejected: a new model for each call (it does not fix a model that the caller passes in, and the issue asks that no caller needs one), a hand-written loop thread (it repeats the portal), and replacing the client after each call (it uses private fields of pydantic_ai).
