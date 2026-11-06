# Proposal

## Why

Issue #3758 is part 3 of #1314. Three slices moved the callers of the `ai`, `k8s` and `argo`, and `security` and `telemetry` packages to the HTTP entry point (`devops_cli.http.entry`). This is the last slice. Ten modules still built their client with `new_http_client` or `new_async_http_client`, and about 25 test files still used `stub_web`, `public_dns`, `scripted_resolver`, `route_client`, `route_llm_clients` or `tests/web_fakes.py`. The old names could not go while one caller needed them.

- Callers: `cloudflare/client.py`, `commands/grafana.py`, `commands/install_tools.py`, `commands/prometheus.py`, `github/session_transport.py`, `roadmap/alternatives.py`, `roadmap/run.py`, `sandbox/metrics.py`, `sandbox/probe.py` and `survey/dependencies.py`.
- Tests: the Cloudflare, Grafana, Prometheus, tool download, Valkey, Vault, sandbox, roadmap, registry and gateway-stall tests, the dashboard Valkey test, the dry-run preview test and the tests of the GitHub session.

## What Changes

- The ten callers build their client with `http_client` or `async_http_client` of `devops_cli.http.entry`. Each keeps its timeouts, headers, event hooks and egress level. The keyword `level=` becomes the first argument.
- The entry point now owns the client construction that `devops_cli.http.client` and `devops_cli.http.pool` held. `devops_cli.http.client` keeps the egress transports, the timeouts and the transport hook of a test. `devops_cli.http.pool` keeps the registry of pooled clients, its reset and its `atexit` close.
- Deleted from `src/`: `new_http_client`, `new_async_http_client`, `get_shared_client` and `get_shared_async_client`.
- Deleted from `tests/`: `tests/web_fakes.py`, `tests/support/web.py` (the `stub_web` and `public_dns` fixtures), `tests/http/test_stub_web.py`, and `route_client`, `route_llm_clients` and `route_retrying_client` of `tests/llm_stream_fakes.py`. The `scripted_resolver` helper goes with `web_fakes.py`.
- Added to `tests/support/fakes/`: `dial.py`. It holds the fake of httpcore2's dial (`record_connects`, `http_response`) that the tests of the egress policy need. This is the layer below the pool, which the `web` fake does not have.
- The GitHub fake (`GitHubApiFake`) installs its transport with `install_transport` and stops patching `httpx2.AsyncClient`. A test that asks for `github_api` and `web` together fails with the error of `install_transport`.
- The tests use the `web` and `dns` fixtures. The files that needed every name to answer a public address ask for `dns` and call `answer_every_name`. Two tests show what changed in what they check:
  - `tests/roadmap/test_roadmap_refine.py` counts the requests of a failing item. The real retry transport now sends a request that gets a 504 five times, where the old helper skipped the retry transport.
  - `tests/http/test_gateway_review_stall.py` runs `LLMClient` over `serve_llm` and the `clock` fixture. The three tests no longer replace private methods of the client or the `httpx2` transport.
- `docs/TESTING.md`, `ARCHITECTURE.md`, `README.md` and the `httpx2` knowledge-base page no longer name the old factories and fakes.
- This change alters no behavior a consumer observes. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request.

## Impact

- `src/devops_cli/http/` (`entry.py`, `client.py`, `pool.py`, `__init__.py`) and the ten callers above.
- About 45 test files, `tests/support/fakes/` and `tests/llm_stream_fakes.py`.
- Not moved, and not named by the acceptance criteria of #3758 as a caller of the old names: the dry-run tests that patch `httpx2.Client.send` or `httpx2.HTTPTransport.handle_request` to prove that a dry run sends nothing (`tests/commands/test_*_dry_run.py`, `tests/github/test_gh_api_status_branch_protection_secrets_dry_run.py`). They patch an httpx2 class, not a devops-cli factory. The `web` fake can prove the same with `web.sent == []`, and that is a separate change of those tests. The same holds for the stubs of internal functions that are not HTTP seams, such as `load_settings`, `_client_args` and `track_request_spend`.

## Feasibility

Checked on `origin/main` e999bfe5, 2026-11-06.

- `rg -n "new_http_client|new_async_http_client|get_shared_client|get_shared_async_client" src` found the ten modules above. After the change it finds nothing. `rg -n "httpx2\.(get|post|put|delete|Client|AsyncClient)\(" src` finds only the two builders in `src/devops_cli/http/entry.py`.
- `http_client(level, ...)` builds the same client as `new_http_client(level=level, ...)` for an unpooled call: `http2` is off unless set, and the timeout, headers, hooks, `follow_redirects` and `transport` arguments pass through. `async_http_client` turns `http2` on unless set, as `new_async_http_client` did. A call with a `key` builds the client that `get_shared_client` built: it follows redirects, uses the default timeout and limits, and turns `http2` on. A pooled call that sets its own timeout, protocol, limits or transport is a `TypeError`, as the pooled client fixes them.
- The GitHub session keeps its own transport semantics. `github/session_transport.py` builds one `httpx2.AsyncClient` at the public level with the connect timeout `DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS`, the API-version header and the origin hook, as before. Only the constructor changed, so `tests/github/test_github_session.py` and `tests/github/test_github_contract.py` hold it.
- A client of the entry point takes the transport of the `web` fixture, also when it is pooled, because `install_transport` closes the pooled clients first (`uv run pytest tests/http/test_entry.py`).
- The `dns` fixture answers the lookup that `vet_addresses` makes and `socket.getaddrinfo` too, so the Valkey, sandbox and Docker-endpoint checks that still call the stdlib lookup get the same answers (`uv run pytest tests/commands/test_valkey.py tests/sandbox`).
- A Hypothesis test cannot take a function-scoped fixture without a health-check setting. `test_property_resolve_hosts_emit_correct_prefix_lengths` sets `HealthCheck.function_scoped_fixture` and scripts its own names for each example, so no state leaks from one example to the next.
- The lost HTTP status of a Claude reply after the retry transport is a separate defect (#3797). This change does not touch it.

## Existing Tool Considered

Not applicable: this change adds no tool and no library. It uses the entry point of #3755 and the `web` and `dns` fixtures of #3755 and #3752, which wrap `httpx2.MockTransport` (open, maintained). `respx` and `pytest-httpx` patch the library and do not know the egress level or the pool, which the test rules of this project refuse; #3755 recorded the same finding. The change deletes the factories, the `stub_web` and `public_dns` fixtures, `ScriptedResolver` and the three `route_*` helpers. The only code it adds is `tests/support/fakes/dial.py`, which is the dial fake that `tests/web_fakes.py` held, moved to the `fakes/` package.
