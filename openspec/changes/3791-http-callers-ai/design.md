# Design

## Context

See proposal.md for the motivation and the scope (#3791, the `ai` slice of #3758). The entry point and the `web` fake are part 2 of #1314 (#3755). The `dns` fixture is part 1 (#3752). The other caller slices and the deletion of the old factories are separate changes.

## Decisions

### 1. `serve_llm` replaces the patches of the private methods of `LLMClient`
- **Decision**: `serve_llm(web, handler)` registers one server on the `web` fake. The server answers a gateway's `GET .../model/info` with `{"data": []}` and keeps that query out of the returned list. It passes every other request to `handler`, records it, and streams a successful JSON chat completion as SSE when the request asks for a stream (`as_requested`). It replaces the servers the test set before it, as `route_client` replaced the transport on each call.
- **Why the `/model/info` answer**: `route_client` patched `devops_cli.ai.gateway._query_model_info` to return None so the query stayed out of the recorded requests. A patch of a `devops_cli` name is the thing this slice removes. An empty list gives the same result for the caller (`fetch_model_info` returns None) and needs no patch. The answer is 200 so that the query does not fall back to `/models`, which `list_models` also reads.
- **Rejected**: keep patching `_shared_client` and `_create_http_client`. They are private, and they hide the pooled client, its retry transport and its egress level, which are the code under test.
- **Rejected**: make the old `route_*` helpers use `web` with the old signature. They take `monkeypatch` and cannot install a fixture-scoped transport without a private patch. Three other slices still call them, so they stay until those slices move.

### 2. Waits go through the `clock` fixture
- **Decision**: a test whose request fails (a 5xx, a connect error) and so wakes the retry transport requests `clock`. Tests of modules with many such cases set `pytestmark = pytest.mark.usefixtures("clock")`.
- **Why**: the real shared client retries five times (waits of 1, 2, 4 and 8 s). `route_retrying_client` set `min_wait=0`; the real client has no such option, and a CI check over 5 minutes is a P0 bug.
- **Rejected**: a `retries=0` setting in each test. It would hide the retry transport, which the tests now exercise.

### 3. A test that needs a client without the retry transport builds one from the entry point
- **Decision**: `LLMClient(..., http_client=http_client(EgressLevel.PRIVATE))` in `test_a_claude_reply_with_a_status_gives_the_status`. The client answers from `web` and has no retry transport.
- **Why**: the shared client's retry transport raises on a 529 before the Anthropic SDK sees the reply, so the status is lost (a separate issue). The test checks the SDK mapping of a reply with a status, which a plain client still shows.
- **Rejected**: weaken the test to expect `None`. That would pin a defect.

### 4. Level checks read the effect, not the transport
- **Decision**: the tests that read `egress_level_of(transport)` now send a request to an address in a private range and check whether it was refused (`SSRFBlockedError`) or reached the fake.
- **Why**: `egress_level_of` reads the private `_pool._network_backend` of a transport. The `web` fake vets each host at the level of the client with `vet_addresses`, so the same question gets the same answer from public behavior.
- **Rejected**: keep `egress_level_of` and read the `web` fake's transport. The fake has no vetting backend to read.

### 5. Three tests keep a patch of `httpcore2.SyncBackend.connect_tcp`
- **Decision**: the three batch-timeout tests of `test_rag_embeddings.py` keep `_dial_gateway`, with the name lookup moved to `dns`.
- **Why**: they check which connections of the pool stay open when a batch times out. The `web` fake replaces the transport above the pool, so it holds no connection to close. A fake peer on a real loopback socket would test the same thing, but needs an HTTP server in the test, which is a different change to the http seam's contract suite.
- **Rejected**: delete the tests. They guard #2011.
