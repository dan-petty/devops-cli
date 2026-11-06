# Design

## Context

See proposal.md for the motivation and the scope (#3755, part 2 of #1314). The DNS seam (part 1) and the migration of the other callers (part 3) are separate changes.

## Decisions

### 1. The seam is httpx2's transport interface, held in `http/client.py`
- **Decision**: `install_transport` takes a function from an egress level to a transport. The factory functions read it when they build a client, so the entry point, the pool and the old factories all take the same transport. A transport of the wrong kind (sync-only for an async client) raises a `TypeError` that names both.
- **Why a function of the level**: the fake must vet a host at the level of the client that sent the request, as the real transport does at the connect. A transport object alone does not know the level.
- **Rejected**: a Protocol of devops-cli's own. It would restate httpx2's transport API, and `httpx2.MockTransport` would not implement it. #1314 decided this on 2026-10-07.
- **Rejected**: patching `httpx2.Client`, as `stub_web` does. A pooled client built before the patch keeps its real transport. The hook closes the pooled clients first.

### 2. One entry point, with a `key` for the pooled case
- **Decision**: `http_client(level, key=...)` and `async_http_client(level, key=...)`. With a `key` the client comes from the pool; the pool fixes its timeout, protocol, limits and transport, so passing one of them with a `key` raises a `TypeError`.
- **Rejected**: a second public function for the pooled case. A caller then picks between two names for one decision.
- **Kept for now**: `new_http_client`, `new_async_http_client`, `get_shared_client` and `get_shared_async_client`. The entry point calls them. About 30 modules still call them, and part 3 moves those callers and deletes the four names. Deleting them here would need those 30 modules in this pull request.

### 3. The broker goes, and its two jobs move to two functions
- **Decision**: `request_headers` adds the User-Agent and the `traceparent` header. `veto_request` (and `aveto_request` for an async client) vetoes a scheme other than http and https, and applies the egress policy of the request to each redirect hop. Vault's request is one call of a pooled private-level client with these two.
- **Rejected**: keep `HttpClientBroker` as a thin class. It has one caller after the move, and a class with a lock and two client maps would repeat the pool.

### 4. `wrapped` is required
- **Decision**: `create_retry_transport(*, wrapped, ...)`. A default transport would dial with no egress check.
- **Rejected**: keep the default and document it. The 2026-10-08 audit of #1314 shows that a caller can omit it with no error.

### 5. The memory profiler hands over its ASGI transport
- **Decision**: `async_http_client(EgressLevel.PRIVATE, transport=httpx2.ASGITransport(...))`. The profiler no longer writes the private `_transport` attribute of a client.

### 6. The fake lives in `tests/support/fakes/http.py`, and `StubWeb` becomes another name of it
- **Decision**: `WebFake` holds the code of `StubWeb`, and adds `answer`, `refuse`, `time_out` and `recorded`. `tests/web_fakes.py` keeps the name `StubWeb` for the 32 test files that use it, until their packages move to `web` in part 3.
- **Rejected**: a second class next to `StubWeb`. Two fakes of one seam would drift apart.
