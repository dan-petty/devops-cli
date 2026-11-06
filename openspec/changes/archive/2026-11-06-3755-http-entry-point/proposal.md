# Proposal

## Why

Issue #3755 is part 2 of #1314. The HTTP clients of devops-cli come from several names, and no test can replace their transport without a patch.

- `HttpClientBroker` and its import-time instance `DEFAULT_HTTP_BROKER` keep their own clients next to the pool of `http/pool.py`. Only two callers use them: `security/vault_http.py`, and `telemetry/memory_profiler.py`, which sets the private `_transport` of its client.
- A test that needs a fake HTTP answer swaps the `httpx2.Client` and `httpx2.AsyncClient` classes (`stub_web`) or sets `HttpClientBroker` internals by hand (`tests/github/test_github_secrets.py`). A pooled client built before the swap keeps its real transport.
- `create_retry_transport` defaults `wrapped` to a plain `httpx2.HTTPTransport()`. That transport has no egress check, so a new caller that omits `wrapped` would dial unchecked.
- No contract suite holds a fake HTTP peer to the real transport.

## What Changes

- `src/devops_cli/http/entry.py` is the one entry point. `http_client` and `async_http_client` build every client: unpooled, or pooled when the caller names a `key`. `request_headers` and `veto_request` give a caller that sends a request itself the User-Agent, the `traceparent` header and the veto of a scheme other than http and https.
- Every client takes its transport from one place, `http/client.py`: the transport that `install_transport` put in place, else the egress transport of its level. The type is httpx2's own transport interface (`httpx2.BaseTransport`, `httpx2.AsyncBaseTransport`). `install_transport` and `remove_transport` close the pooled clients first. The pool keeps its public reset `close_shared_clients` and its `atexit` close.
- Deleted: `http/broker.py` (`HttpClientBroker`, `get_broker`, `DEFAULT_HTTP_BROKER`, `reset_broker`), the private `_transport` write of `memory_profiler.py`, the `http/broker.py` entry of the floor's reset list, and the default transport of `create_retry_transport`. `wrapped` is now a required argument.
- Callers: `security/vault_http.py` (a pooled private-level client with the veto hook), `telemetry/memory_profiler.py` (hands its ASGI transport to the entry point), `ai/client/base.py`, `ai/common_tools.py`, `k8s/service_http.py` and `telemetry/service_status.py` build their clients through the entry point. `security/vault_broker.py` and `security/vault_lease.py` reach HTTP through `vault_http.py`.
- Tests: `tests/support/fakes/http.py` holds `WebFake`, which promotes `StubWeb`, behind the `web` fixture. It answers by method and URL, raises httpx2's connect and read-timeout errors, vets each host with `vet_addresses` at the client's level, and records each request as one value. `tests/http/test_entry_contract.py` runs each case over the fake and over the real egress transport against a loopback server that the test owns. `tests/http/test_entry.py` replaces `tests/http/test_http_broker.py`. The Vault command tests, `tests/github/test_github_secrets.py` and `tests/ai/client/test_gateway_caller_headers.py` use the fake or the hook instead of a patch of the broker.
- `stub_web` stays, answering from `WebFake` (`StubWeb` is another name of it), because the callers that build httpx2 clients inline still use it. The four factory functions stay until the caller migration (part 3 of #1314) removes their last caller. Each has callers today, so this is a planned order, not a shim.
- This change alters no behavior a consumer observes: the commands, their options and messages, and the requests that Vault, the LLM clients and the status pages send are the same. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request. The DNS seam is part 1 of #1314, and the caller migration by package is part 3.

## Impact

- `src/devops_cli/http/` (`entry.py` new, `client.py`, `__init__.py`, `broker.py` deleted), `src/devops_cli/ai/retries/__init__.py`, and the six callers named above.
- `tests/support/fakes/http.py` (new), `tests/http/` (`test_entry.py`, `test_entry_contract.py` and `test_stub_web.py` new, `test_http_broker.py` deleted), `tests/web_fakes.py`, `tests/support/web.py`, `tests/support/fakes/github.py`, `tests/conftest.py` (one line of the reset list), and the test files that used the broker.
- `ARCHITECTURE.md`, `docs/TESTING.md`, `docs/SELF_IMPROVEMENT.md` and the `httpx2` and `tldextract` pages of the knowledge base.

## Feasibility

Checked on `origin/main` 44d9196d, 2026-11-06. The premise of #1314 holds in part. The tree has moved since the issue was written, so each claim was read again.

- The broker exists and has two callers (`rg -n "HttpClientBroker|get_broker|DEFAULT_HTTP_BROKER" src`): `security/vault_http.py:71` and `telemetry/memory_profiler.py:240`. `DEFAULT_HTTP_BROKER` is built at import (`http/broker.py`), but it builds no client and reads no setting then; the egress level is read in `configured_level()` when a client is built (`tests/http/test_http_egress.py`, "the configured level is read from the settings when a client is built").
- `create_retry_transport` still defaults `wrapped` to `httpx2.HTTPTransport()` (`ai/retries/__init__.py`), and its one caller in `src`, `http/client.py`, passes `wrapped`.
- Already done, so this change adds no code for it: no `import httpx` fallback remains in `http/` or in `telemetry/memory_profiler.py` (`rg -n "^\s*import httpx$" src` finds only a prompt file). The User-Agent already comes from the installed release: `user_agent()` in `http/client.py` reads `__version__`, which `config/metadata.py` takes from `pyproject.toml` or, for an installed package, from `importlib.metadata`. `tests/ai/client/test_gateway_caller_headers.py` holds it.
- The list of eight callers in #1314 is out of date. `ai/harness/docs.py` no longer exists, and `security/vault_broker.py` and `security/vault_lease.py` reach HTTP through `security/vault_http.py`. Six modules change: `ai/client/base.py`, `ai/common_tools.py`, `k8s/service_http.py`, `telemetry/service_status.py`, `telemetry/memory_profiler.py` and `security/vault_http.py`. The 30 other modules that call the factories belong to part 3.
- httpx2 2.13 accepts `transport=` for a client, and `httpx2.MockTransport` implements both `BaseTransport` and `AsyncBaseTransport` (`uv run python -c "import httpx2; print(httpx2.MockTransport.__mro__)"`), so the fake needs no devops-cli Protocol.
- The hermetic floor lets a test reach a loopback port that a socket of the test process binds (`tests/conftest.py`, `prevent_external_network_calls`). The contract suite's real side therefore talks to its own `ThreadingHTTPServer`, and to `refusing_port` for a connection that is refused.
- The DNS seam is another agent's part 1. A host that is a name needs a DNS answer, so the `web` fixture requests the existing `public_dns` fixture, as `stub_web` does. The contract suite uses IP literals and needs no lookup.

## Existing Tool Considered

- `httpx2.MockTransport` (httpx2 2.13, open, maintained by the httpx2 project) is the base of the fake: it is the transport interface, so the fake adds only routes, vetting and a record.
- `respx` and `pytest-httpx` mock httpx by patching its transport or its client class. They do not know the egress level, the pool or the `vet_addresses` check, and they patch the library, which the test rules of this project refuse. The transport hook gives the same result with no patch.
- `pytest-httpserver` and the stdlib `ThreadingHTTPServer` serve the real side of the contract. The suite uses the stdlib server, as the OTLP contract suite does, because it needs about 40 lines and no new dependency.
- No library covers a client entry point with an egress level, a pool and a test hook, so the entry point is built. The cost is about 60,000 tokens and one day to build it, and about 5,000 tokens each month to keep it. The change deletes `http/broker.py`, its tests, the broker patches of the Vault tests, and the private `_transport` write of the memory profiler.
