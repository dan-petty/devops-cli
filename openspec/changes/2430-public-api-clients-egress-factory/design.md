# Design

## Decisions

- **The four clients dial at the public level.** Each API host is a fixed public name in the code: `OSVClient.BASE_URL`, `ShodanInternetDBClient.BASE_URL` and `CONST_URL_CLOUDFLARE_API_BASE`. No configuration names a private host for them, so `ai.allow_private_network` does not widen the level. `CloudflareClient` takes a `base_url` argument, but no caller in `src` or `tests` gives it, so the public level applies to each URL that it dials.
- **The timeouts stay the same.** The three lookup clients keep `httpx2.Timeout(self.timeout, connect=1.0)`. The Cloudflare API client gives `read_timeout=30.0`, which the factory turns into `request_timeout(read=30.0)`, the timeout that it had.
- **The Cloudflare API client keeps one client for each request.** `make_request` built a raw client for each attempt and closed it at the end. It now builds a factory client in the same place. A client that the instance keeps would need a close in each caller, which this part does not change.
- **The `transport` argument of `CloudflareRadarClient` goes.** No caller gives it, and the factory takes no transport. The tests of the Radar client patch `httpx2.HTTPTransport.handle_request`, and the factory builds an `httpx2.HTTPTransport`, so these tests do not change.
- **A refusal follows the error path of each client.** The three lookup clients catch each error of the request. Thus a refused lookup gives the same result as a failed connect, and this change does not change these results:
  - `OSVClient` gives a `failed` result and does not cache it.
  - `CloudflareRadarClient` gives the outcome `failed`. It keeps the record in its in-memory cache for the life of the client, and it does not write the record to Valkey.
  - `ShodanInternetDBClient` gives the summary "Unchecked / Lookup timeout" with the outcome `ok`. It keeps the record in its in-memory cache for the life of the client. The outcome `ok` is a defect from before this change: a review shows the address as safe. #2504 fixes it.
- **A `devops cloudflare` command reports a refusal.** `CloudflareClient._request` turns only `httpx2.HTTPError` into `CloudflareAPIError`, so `SSRFBlockedError` goes up to the command. tenacity does not retry it. Each command catches only `CloudflareError`, so before this decision the refusal left the command as an uncaught exception with a traceback. The four command groups (`cloudflare`, `dns`, `tunnel` and `access`) give `exit_on=SSRFBlockedError` to `new_typer`. Thus each command prints the message of the error and exits with its exit code, 2, as the `gh`, `pr` and `openspec` command groups do for their own error type.
- **The clients do not use a proxy from the environment.** httpx2 2.13.1 reads `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` only for a client without a transport (`allow_env_proxies = trust_env and transport is None` in `httpx2/_client.py`). The raw clients had no transport, so they sent their requests through such a proxy. A factory client has a transport, so it dials the API host directly. #898 made this choice for each factory client, and `test_environment_proxies_are_ignored_and_the_destination_dialled` pins it. Thus, on a workstation that gets to the internet only through a proxy, each lookup gives the result of a failed connect, and a `devops cloudflare` command fails. `README.md` already says that factory clients ignore these variables.
- **The test rows are a separate pair of helpers.** `_public_api_calls` and `_public_api_levels` hold the rows of this part, and `_PUBLIC_API_HOSTS` holds the API hosts that the test resolves. The other parts of #1381 add their own helpers to the same tables, so a rebase keeps all the rows.

## Rejected alternatives

- **Give the clients the configured level.** The configured level dials loopback, and private addresses with the flag. These hosts never come from the configuration, and a loopback or private answer for them is a bad DNS answer. The issue gives the public level.
- **Keep the `transport` argument and wrap it in a vetting transport.** The factory owns the transport so that it can put the vetting backend under the pool. A transport from the caller would skip the check. No caller uses the argument.
- **Turn `SSRFBlockedError` into `CloudflareAPIError`.** That hides the security refusal under an API error. The other factory callers let it go up with its own error code.
- **Catch `SSRFBlockedError` in each command handler.** The module has nine handlers that catch `CloudflareError`, and a new handler can forget the second catch. `exit_on` of the command group covers each command of the group, also a new one.
- **Keep the proxy for these four clients.** With a proxy, the factory vets the address of the proxy and not the address of the API host, so the check does not protect the request. Proxy support is a change to the factory for all its callers, not to these four clients.
- **Give a refused InternetDB lookup the outcome `failed` in this change.** The outcome `ok` comes from each failed lookup, also a timeout, not only from a refusal. It is a separate defect with its own test, so #2504 fixes it.

## Non-goals

- The GitHub clients, which #983 moved.
- `_resolve_host_ips` and `_enforce_non_private_ssrf` in `core/validation.py`. Part 5 (#2437) deletes them.
- The general statement that every HTTP client is checked at the connect. Part 5 writes it when it is true.
