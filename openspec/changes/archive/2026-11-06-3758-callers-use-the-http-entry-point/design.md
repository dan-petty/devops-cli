# Design

## Context

See proposal.md for the motivation and the scope (#3758, the last slice). The entry point and the `web` fake are #3755. The `dns` fixture is #3752. The slices for `ai`, `k8s` and `argo`, and `security` and `telemetry` are #3791, #3789 and #3790.

## Decisions

### 1. The entry point owns client construction; `client.py` and `pool.py` keep the parts under it
- **Decision**: `http_client` and `async_http_client` build every client. `devops_cli.http.client` keeps the egress transports, the timeouts, the options type and the transport hook (`set_transport_hook`, `reset_transport_hook`, `has_transport_hook`, `hooked_transport`). `devops_cli.http.pool` keeps `pooled_client`, `pooled_async_client`, `close_shared_clients`, `aclose_shared_clients` and `close_expired_connections`.
- **Why**: the factories in `client.py` and `pool.py` were the second way to build a client. With one builder, the rule "every client comes from the entry point" holds without a list of exceptions.
- **Rejected**: keep `new_http_client` as a thin wrapper of `http_client`. It would be a shim, which an alpha project does not keep.
- **Rejected**: move the pool into `entry.py`. The pool has its own reset and `atexit` close, and its tests, so it stays a module.

### 2. A second transport is an error
- **Decision**: `install_transport` raises `RuntimeError` when a transport is already installed.
- **Why**: the GitHub fake no longer replaces `httpx2.AsyncClient`, so it cannot refuse a second fake. Two fakes of HTTP in one test would let the later one win without a sign. The error is the same check in the one place that installs.
- **Rejected**: let the later install win. A test that asks for `github_api` and `web` would pass or fail by fixture order.

### 3. The dial fake moves to `tests/support/fakes/dial.py`
- **Decision**: `record_connects`, `ConnectRecorder` and `http_response` move from `tests/web_fakes.py` to `tests/support/fakes/dial.py`, with the module docstring that says which layer they fake.
- **Why**: the tests of the egress policy run at the connect, which is below the pool. The `web` fake replaces the transport above the pool, so these tests need a fake of the dial. The sandbox, Vault, Cloudflare, Grafana and Prometheus tests use it to prove that a refused address opens no socket.
- **Rejected**: leave them in `tests/web_fakes.py`. The file existed for the old factories and `stub_web`, and its name no longer says what it holds.

### 4. A test that needs every name public asks for `dns`
- **Decision**: where a test used `public_dns` for its side effect, it asks for `dns` and calls `dns.answer_every_name()`. A module whose tests all need it has one autouse fixture in the file (`test_workload_sandbox.py`, `test_roadmap_implement_step_output_cap.py`). `test_sandbox_network_policy.py` has a `public_address` fixture that also returns the address.
- **Why**: the `web` fixture already answers every name. A shared `public_dns` fixture would keep a second name for the same call.
- **Rejected**: keep `public_dns` in `tests/support/`. The criterion of #3758 is that it goes.

### 5. A request count includes the retries of the real client
- **Decision**: `test_roadmap_refine.py` expects five requests for an item that the gateway answers with a 504 (`_GATEWAY_ATTEMPTS`). The `clock` fixture answers each wait.
- **Why**: `route_llm_clients` replaced the client and so skipped the retry transport. The real client retries a 5xx, so the count of the old test described a client that production does not use.
- **Rejected**: set `max_retries=0` in the test. It would hide the retry transport that the item depends on.
