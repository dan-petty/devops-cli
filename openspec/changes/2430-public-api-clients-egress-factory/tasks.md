# Tasks

## 1. The level test has a row for each public API client

- [x] Add failing rows to `test_each_caller_dials_at_its_level` for the OSV, Shodan InternetDB, Cloudflare Radar and Cloudflare API clients, with and without `ai.allow_private_network`, with the test resolving `api.osv.dev`, `internetdb.shodan.io` and `api.cloudflare.com`
  - Verification: `uv run devops ci test tests/test_http_egress.py`

## 2. The OSV, Shodan InternetDB and Cloudflare Radar clients

- [x] Build the three lookup clients with `new_http_client` at the public level and a 1 s connect timeout, and delete the `transport` argument of `CloudflareRadarClient` with its raw client
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_vulnerability_lookup.py tests/test_security_threat_intel.py`

## 3. The Cloudflare API client

- [ ] Build the client of `CloudflareClient._request` with `new_http_client` at the public level and a 30 s read timeout
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_cloudflare_commands.py`

## 4. Documentation

- [ ] Name the moved clients in `README.md` and in the httpx2 page of the knowledge base
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 5. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2430-public-api-clients-egress-factory`

## Workflow follow-up

- Part 5 (#2437) deletes `_resolve_host_ips` and `_enforce_non_private_ssrf`, and writes the general statement that every HTTP client is checked at the connect.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
