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
- The levels are narrower. A client now refuses a loopback, private or link-local answer for its API host, which it dialled before. A refused lookup of OSV, InternetDB or Radar gives the same result as a failed connect. The design names the result of each client. A refused request of the Cloudflare API client raises `SSRFBlockedError`. The exit seam of `new_typer()` (#2502) reports it: the `devops cloudflare` command prints the message and exits with code 2, with no traceback.
- The four clients no longer send their requests through a proxy from `HTTP_PROXY`, `HTTPS_PROXY` or `ALL_PROXY`, because no factory client does. On a workstation that gets to the internet only through a proxy, the lookups give the result of a failed connect, and the `devops cloudflare` commands fail.
- `classify_network_target` in `ShodanInternetDBClient.check_ip` stays. It decides which addresses the client asks about, not the address that the client dials.
- `README.md` names the moved clients. The other documents that describe the factory make general statements that stay true. The general statement that every HTTP client is checked at the connect waits for part 5 (#2437).
- A consumer sees the refusals, so the change carries a spec delta. It creates the capability `public-api-egress` with three requirements.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `public-api-egress`: the clients of fixed public APIs dial only public addresses, with or without `ai.allow_private_network`, and give the socket the address that they checked. The `devops cloudflare` commands report a refused address with no traceback.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/cloudflare/client.py`. `src/devops_cli/commands/cloudflare.py` does not change, because the exit seam reports the refusal.
- `tests/test_http_egress.py`, `tests/test_cloudflare_commands.py`.
- `README.md`.
- The other callers of these clients do not change: `ai/review/pipeline.py`, `ai/tools/builtin_tools.py` and `security/dependency_remediator.py`.

## Feasibility

- On `origin/main` at `08d70ca6`, `rg -n -g '*.py' 'httpx2\.((Async)?Client|get|post|put|patch|delete|head|request|stream)\(' src/devops_cli/security/vulnerability_lookup.py src/devops_cli/cloudflare/client.py` printed five raw clients: `cloudflare/client.py:366` and `security/vulnerability_lookup.py:217`, `:371`, `:485` and `:487`.
- A scratch script stubbed `socket.getaddrinfo` to answer `10.0.0.1` for `api.osv.dev`, and stubbed `socket.socket.connect` to record the address and refuse. Without `ai.allow_private_network`, `OSVClient().query_package("requests", version="2.0.0", ecosystem="PyPI")` dialled `('10.0.0.1', 443)`.
- The new rows of `test_each_caller_dials_at_its_level` failed on the code before the move, all eight of them. `ConnectRecorder` in `tests/web_fakes.py` got the host name (`api.osv.dev`, `internetdb.shodan.io` or `api.cloudflare.com`) from each raw client, so the socket resolved the name with no check.
- The factory (`new_http_client` in `devops_cli.http.client`) takes `timeout=httpx2.Timeout(...)` as it is, and `read_timeout=30.0` gives `request_timeout(read=30.0)`. It takes no transport. httpx2 and httpcore2 are 2.13.1.
- tenacity 9.1.4 `retry_if_result` returns `False` for a failed outcome (`tenacity/retry.py`). Thus `CloudflareClient._request` does not retry a refusal, and the `SSRFBlockedError` goes up once.
- `SSRFBlockedError` is a `SecurityError`, and thus a `DevOpsCLIError`, with exit code 2 (`exceptions/security.py`). On `origin/main` at `305d3ba0`, the exit seam of `OTelTyper.command` (#2502) reports each `DevOpsCLIError` of a command in one line, with no traceback. With the factory client and a `10.0.0.1` answer for `api.cloudflare.com`, `devops cloudflare status`, `dns list`, `tunnel routes` and `access status` each print the `SSRF blocked` message and exit 2, and the socket gets neither `10.0.0.1` nor `api.cloudflare.com`. The rows of `test_cli_cloudflare_refused_address_is_reported` pass on that code. Before the move of the Cloudflare API client, they fail: the command exits 1, and the socket gets the host name `api.cloudflare.com`.
- httpx2 2.13.1 reads the proxy variables only when `trust_env and transport is None` (`httpx2/_client.py:659`). The raw clients had no transport, and a factory client has one.

## Existing Tool Considered

The change uses the egress-checked factory of #898 (`devops_cli.http.client`), which builds on the httpcore2 network backend API. It builds no new check. It deletes these internal paths: the five raw `httpx2.Client` builds in the table and the `transport` argument of `CloudflareRadarClient`, with the branch that built a raw client around it.
