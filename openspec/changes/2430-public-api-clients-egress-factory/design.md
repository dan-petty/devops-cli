# Design

## Decisions

- **The four clients dial at the public level.** Each API host is a fixed public name in the code: `OSVClient.BASE_URL`, `ShodanInternetDBClient.BASE_URL` and `CONST_URL_CLOUDFLARE_API_BASE`. No configuration names a private host for them, so `ai.allow_private_network` does not widen the level. `CloudflareClient` takes a `base_url` argument, but no caller in `src` or `tests` gives it, so the public level applies to each URL that it dials.
- **The timeouts stay the same.** The three lookup clients keep `httpx2.Timeout(self.timeout, connect=1.0)`. The Cloudflare API client gives `read_timeout=30.0`, which the factory turns into `request_timeout(read=30.0)`, the timeout that it had.
- **The Cloudflare API client keeps one client for each request.** `make_request` built a raw client for each attempt and closed it at the end. It now builds a factory client in the same place. A client that the instance keeps would need a close in each caller, which this part does not change.
- **The `transport` argument of `CloudflareRadarClient` goes.** No caller gives it, and the factory takes no transport. The tests of the Radar client patch `httpx2.HTTPTransport.handle_request`, and the factory builds an `httpx2.HTTPTransport`, so these tests do not change.
- **A refusal follows the error path of each client.** The three lookup clients catch each error of the request and give a failed result, so a refused lookup is `failed` and is not cached. `CloudflareClient._request` turns only `httpx2.HTTPError` into `CloudflareAPIError`. `SSRFBlockedError` is a `DevOpsCLIError`, so the command reports it with its error code, as part 1 (#2422) does for its callers. tenacity does not retry it.
- **The test rows are a separate pair of helpers.** `_public_api_calls` and `_public_api_levels` hold the rows of this part, and `_PUBLIC_API_HOSTS` holds the API hosts that the test resolves. The other parts of #1381 add their own helpers to the same tables, so a rebase keeps all the rows.

## Rejected alternatives

- **Give the clients the configured level.** The configured level dials loopback, and private addresses with the flag. These hosts never come from the configuration, and a loopback or private answer for them is a bad DNS answer. The issue gives the public level.
- **Keep the `transport` argument and wrap it in a vetting transport.** The factory owns the transport so that it can put the vetting backend under the pool. A transport from the caller would skip the check. No caller uses the argument.
- **Turn `SSRFBlockedError` into `CloudflareAPIError`.** That hides the security refusal under an API error. The other factory callers let it go up with its own error code.

## Non-goals

- The GitHub clients, which #983 moved.
- `_resolve_host_ips` and `_enforce_non_private_ssrf` in `core/validation.py`. Part 5 (#2437) deletes them.
- The general statement that every HTTP client is checked at the connect. Part 5 writes it when it is true.
