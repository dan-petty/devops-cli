# Tasks

## 1. Clients come from one entry point with a transport hook (behavior)

- [x] 1.1 Add the contract suite: the same cases over `WebFake` and over the real egress transport against a loopback server (status, headers and body; JSON; redirects and their limit; a refused connection; a read timeout; a destination that SSRF validation refuses, before any request), sync and async
  - Verification: `uv run devops ci test tests/http/test_entry_contract.py`
- [x] 1.2 Add failing tests: pooled and unpooled clients, the options a pool fixes, the hook, the close of the pooled clients on a swap, a retrying client on the seam's transport, a required `wrapped`, the request headers and the veto
  - Verification: `uv run devops ci test tests/http/test_entry.py`
- [x] 1.3 Add `http/entry.py` and the transport hook of `http/client.py`, and make `wrapped` of `create_retry_transport` required
  - Verification: `uv run devops ci test tests/http/ tests/ai/retries/`
- [x] 1.4 Add `tests/support/fakes/http.py` with `WebFake` and the `web` fixture, and make `StubWeb` another name of `WebFake`
  - Verification: `uv run devops ci test tests/http/ tests/security/test_vault_broker.py`

## 2. The broker and the private transport write are gone (refactor)

- [x] 2.1 Move `security/vault_http.py`, `telemetry/memory_profiler.py`, `ai/client/base.py`, `ai/common_tools.py`, `k8s/service_http.py` and `telemetry/service_status.py` to the entry point
  - Verification: `uv run devops ci test tests/commands/test_vault_cmd.py tests/commands/test_memory_profiler.py tests/security/ tests/k8s/`
- [x] 2.2 Delete `http/broker.py` and the broker entry of the floor's reset list, move the broker tests to the entry point and the `web` fixture, and move the Vault command tests, the GitHub secrets test and the user-agent test off the broker patches
  - Verification: `! git grep -nE "HttpClientBroker|get_broker|DEFAULT_HTTP_BROKER|reset_broker|http\.broker" -- src tests ':!tests/fixtures'`

## 3. Documents

- [x] 3.1 Describe the entry point, the hook and the `web` fixture in `ARCHITECTURE.md`, `docs/TESTING.md` and the knowledge base, and drop the row about the broker from `docs/SELF_IMPROVEMENT.md`
  - Verification: `uv run devops ci docs`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3755-http-entry-point`

## Workflow follow-up

- #1314 part 1 adds the DNS seam and its `dns` fixture. The `web` fixture then requests `dns` in place of `public_dns`.
- #1314 part 3 moves the other callers of the four factory functions to the entry point, moves the tests that use `stub_web` to `web`, and deletes the four names, `stub_web` and `tests/web_fakes.py`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
