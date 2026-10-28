# Proposal

## Why

Issue #2430 is part 3 of the split of #1381. The clients of four fixed public APIs build a raw `httpx2.Client`, and they make no address check. httpx2 resolves the API host at the socket and dials each answer. Thus a bad or rebinding DNS answer for `api.osv.dev` can send the request to a loopback, private or link-local address. For the Cloudflare clients, the request also sends the Cloudflare API token to that address. #898 closed this gap for the callers that it moved to the egress-checked factory (`devops_cli.http.client`). This change moves the four clients to the factory at the public level.

| Caller | Client before | Pre-flight check that goes | Level after |
| :--- | :--- | :--- | :--- |
| OSV (`api.osv.dev`), `OSVClient` | raw `httpx2.Client` | none | public |
| Shodan InternetDB (`internetdb.shodan.io`), `ShodanInternetDBClient` | raw `httpx2.Client` | none | public |
| Cloudflare Radar (`api.cloudflare.com`), `CloudflareRadarClient` | raw `httpx2.Client`, also around a `transport` argument | none | public |
| Cloudflare API (`api.cloudflare.com`), `CloudflareClient._request` | raw `httpx2.Client` for each request | none | public |

The public level admits only public addresses. `ai.allow_private_network` does not change it. Cloud metadata addresses are refused at every level.

## What Changes

- Each client in the table gets its client from `new_http_client(level=EgressLevel.PUBLIC, ...)`. The client resolves the API host one time, at the connect, and dials only public addresses. The factory checks each redirect hop in the same way.
- The timeouts stay the same: a 1 s connect timeout for the three lookup clients, and `request_timeout(read=30.0)` for the Cloudflare API client.
- The `transport` argument of `CloudflareRadarClient` is deleted. No caller in `src` or `tests` gives it, and the factory takes no transport.
- The levels are narrower. A client now refuses a loopback, private or link-local answer for its API host, which it dialled before. A refused lookup of OSV, InternetDB or Radar gives a failed result, as a failed connect does. A refused request of the Cloudflare API client raises `SSRFBlockedError` to the `devops cloudflare` command.
- `classify_network_target` in `ShodanInternetDBClient.check_ip` stays. It decides which addresses the client asks about, not the address that the client dials.
- `README.md` and the httpx2 page of the knowledge base name the moved clients. The general statement that every HTTP client is checked at the connect waits for part 5 (#2437).
- A consumer sees the refusals, so the change carries a spec delta. It creates the capability `public-api-egress` with two requirements.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `public-api-egress`: the clients of fixed public APIs dial only public addresses, with or without `ai.allow_private_network`, and give the socket the address that they checked.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/cloudflare/client.py`.
- `tests/test_http_egress.py`.
- `README.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/httpx2.md`.
- The callers of these clients do not change: `ai/review/pipeline.py`, `ai/tools/builtin_tools.py`, `security/dependency_remediator.py` and `commands/cloudflare.py`.

## Feasibility

- On `origin/main` at `08d70ca6`, `rg -n -g '*.py' 'httpx2\.((Async)?Client|get|post|put|patch|delete|head|request|stream)\(' src/devops_cli/security/vulnerability_lookup.py src/devops_cli/cloudflare/client.py` printed five raw clients: `cloudflare/client.py:366` and `security/vulnerability_lookup.py:217`, `:371`, `:485` and `:487`.
- A scratch script stubbed `socket.getaddrinfo` to answer `10.0.0.1` for `api.osv.dev`, and stubbed `socket.socket.connect` to record the address and refuse. Without `ai.allow_private_network`, `OSVClient().query_package("requests", version="2.0.0", ecosystem="PyPI")` dialled `('10.0.0.1', 443)`.
- The new rows of `test_each_caller_dials_at_its_level` failed on the code before the move, all eight of them. `ConnectRecorder` in `tests/web_fakes.py` got the host name (`api.osv.dev`, `internetdb.shodan.io` or `api.cloudflare.com`) from each raw client, so the socket resolved the name with no check.
- The factory (`new_http_client` in `devops_cli.http.client`) takes `timeout=httpx2.Timeout(...)` as it is, and `read_timeout=30.0` gives `request_timeout(read=30.0)`. It takes no transport. httpx2 and httpcore2 are 2.13.1.
- tenacity 9.1.4 `retry_if_result` returns `False` for a failed outcome (`tenacity/retry.py`). Thus `CloudflareClient._request` does not retry a refusal, and the `SSRFBlockedError` goes up once.

## Existing Tool Considered

The change uses the egress-checked factory of #898 (`devops_cli.http.client`), which builds on the httpcore2 network backend API. It builds no new check. It deletes these internal paths: the five raw `httpx2.Client` builds in the table and the `transport` argument of `CloudflareRadarClient`, with the branch that built a raw client around it.
