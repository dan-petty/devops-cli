# Task 324: Asynchronous HTTP/2 Connection Multiplexing, Lifespan Handlers & OpenAPI 3.1 Synchronization Research

**Issue**: [#324](https://github.com/dan-petty/devops-cli/issues/324)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

The prevailing pattern across the codebase — 60 sites — was:

```python
with httpx2.Client(timeout=...) as client:
    client.post(url, json=payload)
```

which builds a connection pool, performs one request, and tears the pool down. Every call
therefore paid for a fresh TCP handshake and a fresh TLS negotiation. Measured against real
endpoints before any change:

| Endpoint | Client per call | Shared client | Speedup |
| --- | --- | --- | --- |
| Cluster API (LAN) | 19 ms/req | 12 ms/req | 1.5× |
| `api.github.com` (WAN) | 247 ms/req | 61 ms/req | **4.1×** |

### Key Deliverables Completed:

- [x] **Shared Client Registry (`src/devops_cli/http/pool.py`)**: clients keyed on *transport*
  configuration only — TLS material, redirects, protocol — because that is what a connection
  can be shared across. Anything varying per call (headers, per-request timeout) is passed to
  the request, so an authorization header does not fragment the pool into a client per caller.
- [x] **HTTP/2 and Bounded Limits**: every shared client negotiates HTTP/2 and carries explicit
  connection limits. Reusing connections without a ceiling trades connection churn for
  descriptor exhaustion, which is the failure this is supposed to prevent rather than cause.
- [x] **Lifecycle**: `close_shared_clients` is registered with `atexit`, so a long-lived pool
  does not outlive the process that built it.
- [x] **Migrated the Repeated-Call Paths**: the cluster service proxy (one request per dashboard
  panel per refresh) and the LLM providers (one per inference).
- [x] **Removed Two More Per-Call Rebuilds Found By Measuring**: pooling alone left the proxied
  request at 25 ms, so the remaining cost was attributed rather than assumed —
  `resolve_proxy_target` reloaded and reparsed the kubeconfig every call (24 ms), and
  `resolve_context` reloaded settings every call (10.8 ms). Both are now cached against the
  modification time of the file they read, which keeps the freshness property each was written
  for while removing the reload.
- [x] **Centralized Constants**: connection limits, keep-alive expiry.
- [x] **Automated Tests & Quality Gates**:
  - 23 tests in `tests/test_http_connection_pool.py` using structural tuple equality assertions.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

End-to-end, against the live cluster, measured by stashing the change and re-running:

```
--- BEFORE (release/v0.2.22) ---  34 ms/req
--- AFTER ---                     13 ms/req
```

**2.6× on the proxied request path**, which the dashboard issues once per panel per refresh.

## A Regression The Existing Suite Caught

Moving the timeout from the client to the request is required — a shared client cannot carry
one caller's timeout — and the first version of that change dropped it from the Ollama chat
call entirely. Every long review would have aborted at the generic HTTP timeout instead of the
review timeout. `test_review_client_uses_long_read_timeout_for_chat_requests` failed, which is
exactly what it existed for. All four call sites now pass an explicit timeout, and the test
asserts it at the request, where it now takes effect.

## Design Constraint: Attribute Cost, Do Not Assume It

Pooling was the stated deliverable, but after applying it the proxied request was still 25 ms,
and the assumption that HTTP dominated would have stopped the work there. Profiling attributed
24 ms to kubeconfig reloading and 10.8 ms to settings reloading — both larger than the HTTP.
The same discipline applies to what was *not* done below.

## Scope Note

**`load_settings` remains uncached globally.** It costs 10.8 ms per call and is used across the
whole codebase, so caching it centrally would be a wide behavioural change to settings
mutability — and this session has already fixed one stale-settings defect caused by capturing a
snapshot. The narrow cache added here is confined to the Kubernetes context resolver, keyed on
the configuration file's modification time. A general fix is recorded in `docs/ROADMAP.md`.

**FastAPI lifespan handlers and OpenAPI 3.1 client SDK generation were not implemented.** The
measured defect was outbound connection churn, not server lifespan; `serve.py` holds no
long-lived outbound clients whose lifetime a lifespan handler would manage. SDK generation is a
separate deliverable with no consumer in this repository today, and shipping a generator nobody
calls is an unexercised path.
