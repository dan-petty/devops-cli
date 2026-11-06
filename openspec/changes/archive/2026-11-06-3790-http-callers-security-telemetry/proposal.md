# Proposal

## Why

Issue #3790 is one slice of #3758, which is part 3 of #1314. After the HTTP entry point (#3755) and the DNS seam (#3752), four modules of `security/` and `telemetry/` still build their client with `new_http_client`, and the tests of these packages still replace the transport by hand.

- Callers: `security/vulnerability_lookup.py` (OSV, Shodan InternetDB and Cloudflare Radar, through `_public_api_client`), `security/semgrep_registry.py`, `telemetry/exporter.py` (the OTLP/HTTP exporter) and `telemetry/waterfall.py` (the Tempo query).
- Tests: `test_vulnerability_lookup.py` scripts the resolver with `scripted_resolver`, dials through `record_connects`, and patches `httpx2.HTTPTransport.handle_request` with a hand-built `httpx2.MockTransport`. `test_sandbox_traces.py` replaces `httpx2.Client` with classes it writes and patches `socket.getaddrinfo`. `test_network_security.py`, `test_reference_extraction.py` and `test_reference_address_classes.py` patch `socket.getaddrinfo`. Six more files take the `stub_web` fixture.
- The tests of `query_tempo_trace` sit in `tests/telemetry/test_sandbox_traces.py`, not in the mirror of `telemetry/waterfall.py`.

## What Changes

- The four callers build their client with `http_client` of `devops_cli.http.entry`. Each keeps its egress level (public for OSV, Shodan, Radar and the Semgrep registry; private for the collector; loopback for Tempo), its timeouts and its error handling. The exporter keeps the import inside the function, because `devops_cli.http` imports the tracer, which imports the exporter.
- Every test of the two packages uses the `web` and `dns` fixtures. This includes the tests of `check_threat_intel` and `scan_osv` in `tests/security/test_builtin_tools.py`, which assert `web.sent == []` or fail the OSV URL with `web.fail`. The Shodan cases answer from `web` (`answer`, `refuse`) and script the API host with `dns.add`. The Radar cases answer with `web.respond` and read the request from `web.recorded`. The tests that held no lookup now read `dns.lookups`.
- The tests of `query_tempo_trace` move to the new `tests/telemetry/test_waterfall.py`. They no longer assert the address that the client dialled or the TLS server name: those are the work of the transport, and `tests/http/test_http_egress.py` holds them for the Tempo client at the loopback level.
- Deleted: the `scripted_resolver`, `record_connects` and `http_response` uses, the hand-built `MockTransport` patches, the `httpx2.Client` classes of the tests and the `socket.getaddrinfo` patches in these two packages. The old factories, `stub_web`, `public_dns` and `tests/web_fakes.py` stay for the other slices of #3758, which delete them with their last caller.
- This change alters no behavior a consumer observes: the same requests go to the same hosts at the same egress levels, and the commands print the same text. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request.

## Impact

- `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/security/semgrep_registry.py`, `src/devops_cli/telemetry/exporter.py`, `src/devops_cli/telemetry/waterfall.py`.
- `tests/security/` (eleven files) and `tests/telemetry/` (`test_sandbox_traces.py` changed, `test_waterfall.py` new).
- No document changes: `docs/TESTING.md` already says that `stub_web` stays until its package moves, and the factories stay until the last caller moves.

## Feasibility

Checked on `origin/main` 27c7019f, 2026-11-06. The premise of #3758 holds for this slice, and the list of callers in it is out of date, so each claim was read again.

- Four non-test callers remain in the two packages (`rg -n "new_http_client|new_async_http_client|get_shared_client|get_shared_async_client|httpx2\.(get|post|Client)" src/devops_cli/security src/devops_cli/telemetry`): `vulnerability_lookup.py:218`, `semgrep_registry.py:171`, `exporter.py:164` and `waterfall.py:167`. `security/vault_http.py`, `telemetry/service_status.py` and `telemetry/memory_profiler.py` moved with #3755. No module of the two packages calls `socket.getaddrinfo`, so the resolver seam needs no source change here.
- `http_client` has the same defaults as `new_http_client` for these callers: no pool without a `key`, `http2` off, and the same `timeout` and `read_timeout` arguments (`src/devops_cli/http/entry.py`). The exporter keeps an unpooled client that it owns and closes.
- `WebFake` vets each host with `vet_addresses` at the level of the client, as the real transport does at the connect, and the `dns` fixture answers the lookup. A refused answer (a private address for the Shodan host) therefore fails before any request is recorded.
- The fake differs from the real transport in one case: a URL with a scheme other than http and https (`ftp://example.com`) reaches the fake, while httpx2 refuses it in the real transport. The test of `query_tempo_trace` does not check the scheme. `test_the_veto_refuses_a_scheme_other_than_http` in `tests/http/test_entry.py` holds that rule. The test of the caller asserts that a private address, a metadata address and an unsafe trace ID send no request.
- The tests that asserted the dialled address and the TLS server name of the Tempo client duplicate `tests/http/test_http_egress.py` (`recorder.dialled`, `recorder.tls`, `recorder.requested_hosts`), so they are not kept in the caller test.

## Existing Tool Considered

Not applicable: this change adds no tool and no library. It moves callers onto the entry point of #3755 and the tests onto the `web` fixture of #3755 and the `dns` fixture of #3752. `httpx2.MockTransport` stays the base of `WebFake`. The change deletes test code that did the same work by hand: the resolver script, the connect recorder and the transport patches in these packages.
