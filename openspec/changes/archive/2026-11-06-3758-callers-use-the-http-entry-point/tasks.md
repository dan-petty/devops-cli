# Tasks

## 1. The last callers build their client at the entry point (refactor)

- [x] 1.1 Move `cloudflare/client.py`, `commands/grafana.py`, `commands/install_tools.py`, `commands/prometheus.py`, `github/session_transport.py`, `roadmap/alternatives.py`, `roadmap/run.py`, `sandbox/metrics.py`, `sandbox/probe.py` and `survey/dependencies.py` to `http_client` and `async_http_client`
  - Verification: `! git grep -n -w new_http_client -- src`, `! git grep -n -w new_async_http_client -- src`, `! git grep -n -w get_shared_client -- src`, `! git grep -n -w get_shared_async_client -- src`
- [x] 1.2 Delete `new_http_client`, `new_async_http_client`, `get_shared_client` and `get_shared_async_client`, and their exports; the entry point builds every client
  - Verification: `uv run pytest -n0 tests/http`

## 2. The tests use the `web` and `dns` fixtures (test-only edits)

- [x] 2.1 Move the GitHub fake to `install_transport`, and the dial fake to `tests/support/fakes/dial.py`
  - Verification: `uv run pytest -n0 tests/github tests/http/test_entry.py`
- [x] 2.2 Move the tests that used `stub_web`, `public_dns`, `scripted_resolver`, `route_client` and `route_llm_clients` to `web`, `dns` and `serve_llm`
  - Verification: `! git grep -n -w stub_web -- 'tests/*.py'`, `! git grep -n -w StubWeb -- 'tests/*.py'`, `! git grep -n -w public_dns -- 'tests/*.py'`, `! git grep -n -w scripted_resolver -- 'tests/*.py'`, `! git grep -n -w web_fakes -- 'tests/*.py'`, `! git grep -n -w route_client -- 'tests/*.py'`, `! git grep -n -w route_llm_clients -- 'tests/*.py'`, `! git grep -n -w route_retrying_client -- 'tests/*.py'`
- [x] 2.3 Move the Cloudflare client tests and the Grafana sync tests from patches of `httpx2.Client` to `web`
  - Verification: `uv run pytest -n0 tests/commands/test_cloudflare_commands.py tests/commands/test_grafana.py`
- [x] 2.4 Delete `tests/web_fakes.py`, `tests/support/web.py`, `tests/http/test_stub_web.py` and the three `route_*` helpers
  - Verification: `! git grep -n -F 'def route_client' -- 'tests/*.py'`, `! git grep -n -F 'def stub_web' -- 'tests/*.py'`

## 3. Documents (documents)

- [x] 3.1 Remove the old factories and fakes from `docs/TESTING.md`, `ARCHITECTURE.md`, `README.md` and the `httpx2` knowledge-base page
  - Verification: `! git grep -n -w new_http_client -- docs ARCHITECTURE.md README.md src`, `! git grep -n -w new_async_http_client -- docs ARCHITECTURE.md README.md src`, `! git grep -n -w get_shared_client -- docs ARCHITECTURE.md README.md src`, `! git grep -n -w get_shared_async_client -- docs ARCHITECTURE.md README.md src`, `! git grep -n -w stub_web -- docs ARCHITECTURE.md README.md src`, `! git grep -n -w scripted_resolver -- docs ARCHITECTURE.md README.md src`
- [x] 3.2 Check that the change folder is valid
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- The dry-run tests that patch `httpx2.Client.send` or `httpx2.HTTPTransport.handle_request` to prove that a dry run sends nothing stay as they are. A later change can move them to `web.sent == []`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
