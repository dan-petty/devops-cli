# Tasks

## 1. The callers build their client through the entry point (refactor)

- [x] 1.1 Move `security/vulnerability_lookup.py`, `security/semgrep_registry.py`, `telemetry/exporter.py` and `telemetry/waterfall.py` to `http_client` of `devops_cli.http.entry`
  - Verification: `! git grep -nE "new_http_client|new_async_http_client|get_shared_client|get_shared_async_client" -- src/devops_cli/security src/devops_cli/telemetry`

## 2. The tests use the `web` and `dns` fixtures (refactor)

- [x] 2.1 Move the tests of the Semgrep registry, Vault, the dependency remediator, the threat intelligence and the vulnerability lookup from `stub_web`, `scripted_resolver`, `record_connects` and the transport patches to `web` and `dns`
  - Verification: `uv run devops ci test tests/security/`
- [x] 2.2 Move the tests of `query_tempo_trace` from `tests/telemetry/test_sandbox_traces.py` to `tests/telemetry/test_waterfall.py`, on `web` and `dns`
  - Verification: `uv run devops ci test tests/telemetry/`
- [x] 2.3 Move the tests that patched `socket.getaddrinfo` in `tests/security/` to `dns`
  - Verification: `! git grep -nE "stub_web|StubWeb|public_dns|scripted_resolver|record_connects|web_fakes|getaddrinfo|MockTransport|HTTPTransport|httpx2\.Client" -- tests/security tests/telemetry`

## 3. Archive

- [x] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 3790-http-callers-security-telemetry`
