# Proposal

## Why

Issue #3791 is the first caller slice of #3758, part 3 of #1314. After the HTTP entry point of part 2 (`devops_cli.http.entry`), seven modules of `src/devops_cli/ai/` still build their client with `new_http_client` or `new_async_http_client`. About 50 test files of `tests/ai/` and `tests/review/` reach those clients with `stub_web`, `public_dns`, `scripted_resolver`, `record_connects`, patches of `httpx2.Client` methods, `MockTransport` clients built by hand, and patches of the private client methods of `LLMClient`. Each of these needs a patch that a pooled client built earlier can bypass, and the `web` and `dns` fixtures replace them all.

- Source: `ai/gateway.py` (four clients), `ai/pool_load.py`, `ai/library/docs_ingester.py`, `ai/providers/__init__.py`, `ai/models/ollama.py`, `ai/rag/embeddings.py` and `ai/spend/pricing.py`.
- Tests: the replies of a model, of a gateway, of Ollama, of the pricing registry, of Loki, of a docs site and of an embedding server come from the `web` fake. The names that these tests resolve come from the `dns` fixture.

## What Changes

- The seven modules build their client with `http_client(level, ...)` or `async_http_client(level, ...)`. Each keeps its timeouts, its headers, its event hooks and its egress level. This is a rename of the constructor and a change of the keyword `level=` into the first argument. `ai/client/base.py` and `ai/common_tools.py` already used the entry point (#3755).
- `tests/llm_stream_fakes.py` gains `serve_llm(web, handler)`. It answers every request of a model client from `handler`, streams a JSON chat completion as SSE when the request asks for a stream, answers the `/model/info` query of a gateway with an empty list, and returns the requests it served. `streamed` takes the `web` fake. `route_client`, `route_llm_clients` and `route_retrying_client` stay for `tests/roadmap`, `tests/core` and `tests/http`, which other slices of #3758 move.
- The tests of `tests/ai/` and `tests/review/` use `web` (and `dns` where a test needs a name to answer a private address or a script). A test that needs the retry transport to wait uses the `clock` fixture.
- Four tests change what they check, because the real client is now under test:
  - A Claude reply with HTTP 529 loses its status when the retry transport is on (the SDK sees the transport error, not the reply). The test builds a client from `http_client` without retries and gives it to `LLMClient`. A separate issue records the lost status.
  - The test of the failover of the Ollama servers sets `max_retries=0`, so each server gets one try, as the test says.
  - The tests of the egress level of the providers (`test_pydantic_ai_ollama`, `test_pydantic_ai_profiles_and_providers`, `test_ai_client_retries`) read the level from the behavior of a request to an address in a private range, not from the private pool of the transport. A new test shows that the shared client waits and sends again after a 503.
- No command, option, message or request changes. The change has no spec delta, and `skip_specs: true` is set.
- The change fits one pull request.

## Impact

- `src/devops_cli/ai/` (seven modules and one knowledge-base page).
- `tests/llm_stream_fakes.py`, `docs/TESTING.md`, and about 50 test files of `tests/ai/` and `tests/review/`.
- Left to other slices of #3758: the callers outside `ai/`, the other users of `route_*`, and the deletion of `new_http_client`, `new_async_http_client`, `get_shared_client`, `get_shared_async_client`, `stub_web`, `public_dns`, `ScriptedResolver` and `tests/web_fakes.py`.

## Feasibility

Checked on `origin/main` 27c7019f, 2026-11-06. The list of callers in #3758 is out of date, so each claim was read again.

- Callers: `rg -n "new_http_client|new_async_http_client|get_shared_client|get_shared_async_client" src/devops_cli/ai` finds the seven modules above (`ai/client/base.py` and `ai/common_tools.py` already use `http_client`). `rg -n "getaddrinfo|import socket" src/devops_cli/ai` finds nothing, so no DNS caller moves.
- `http_client(level, ...)` builds the same client as `new_http_client(level=level, ...)` for an unpooled call: it passes `http2=bool(http2)` (False when unset, as `new_http_client` defaults) and the other options. `async_http_client` passes `http2` on unless set, as `new_async_http_client` does (`src/devops_cli/http/entry.py`).
- A client built through the entry point takes the transport of the `web` fixture, also when it is pooled (`install_transport` closes the pooled clients first). So the clients that `LLMClient` shares (`key="llm:..."`) answer from the fake, and no test patches `_shared_client` or `_create_http_client`.
- The real retry transport now runs in those tests. A 4xx or 5xx reply raises `httpx2.HTTPStatusError`, and a connect error is sent again after a wait (`uv run pytest tests/ai/client/test_ai_client_retries.py`). Waits go through `devops_cli.core.clock.sleep`, which the `clock` fixture answers at once, so no test waits. Tests that never fail a request do not need the fixture.
- One test file keeps a patch of an `httpcore2` backend: three tests of `tests/ai/rag/test_rag_embeddings.py` (`_dial_gateway`) check that a timed-out batch leaves the connections of the parallel batches open. That needs a real connection pool over a fake socket, which the `web` fake does not have (it replaces the transport above the pool). The names they resolve now come from `dns`.
- Out of scope, so left as they are: the stubs of internal functions that are not HTTP seams (`fetch_model_info` in `test_ai_gateway_tune.py` and `test_thinking_providers.py`, `_make_review_clients`, the spend patches), the Qdrant client in `test_rag_query_telemetry.py`, which uses `qdrant_client`'s own httpx transport, and `ai/review/runner.py`, which gives `LLMClient` a `MockTransport` on purpose to preview a request without sending it.
- The claimed lost status of a Claude reply (see What Changes) was seen with `uv run pytest tests/ai/client/test_ai_client_error_reason.py` before the test was changed: `error.status` was `None` for HTTP 529 through the shared retrying client.

## Existing Tool Considered

The slice adds no tool. It uses the entry point and the `web` and `dns` fixtures of #3755 and #3752, which wrap `httpx2.MockTransport` (open, maintained). `respx` and `pytest-httpx` patch the library and do not know the egress level or the pool, which the test rules of this project refuse; #3755 recorded the same finding. The change deletes no code of its own beyond the patches in the tests; the old factories go in the last slice of #3758.
